# Design: ArgoCD → ServiceNow Change Request Automation

**Status:** Draft v0.2 — decisions resolved 2026-07-02
**Scope:** Automated CR lifecycle (create → start → close → attach-audit) driven by Akuity ArgoCD sync events, enriched with ArgoCD-sourced audit data, delivered to the existing ServiceNow CR API.

---

## 1. Problem Statement

The existing change automation follows a create → start → close → attach-audit lifecycle against ServiceNow via an internal API. We need the same lifecycle driven by GitOps deployments: an ArgoCD sync operation *is* the change, so ArgoCD events must map onto the CR lifecycle, with audit data assembled from ArgoCD sync results.

Auto-sync is **disabled** on all production Applications. Every sync is a deliberate, manually-initiated action. The primary audit requirement is tracking **who clicked sync**, which is captured directly in `operationState.operation.initiatedBy.username`.

---

## 2. Design Overview

```
┌──────────────────────┐   REST API polling    ┌──────────────────┐   REST    ┌────────────────┐
│ Akuity               │  (List Apps,          │  change-bridge    │──────────▶│ Existing SNOW  │
│ ArgoCD (Cloud)       │   one call/15s)       │  service          │           │ CR API         │
│ /api/v1/...          │◀─────────────────────│  (Python/uv)      │           └────────────────┘
└──────────────────────┘                       │                   │
                                               │  - state diff     │
                                               │  - CR lifecycle   │
                                               │  - idempotency    │
                                               └──────────────────┘
                                                        │
                                                 ┌──────▼──────────┐
                                                 │ In-cluster HA   │
                                                 │ Redis (WUS3)    │
                                                 │ operationKey    │
                                                 │ state + timers  │
                                                 └─────────────────┘
```

Two components:

1. **Akuity API** — Single polling endpoint: `GET /api/v1/orgs/{org}/instances/{instance}/applications?selector=env=prod` returns full Application state (including `operationState`) for all prod apps in one call.
2. **change-bridge service** — Python service on WUS3 cluster (`snow-bridge-gitops` namespace) that polls every 15s, detects state transitions, maps them to CR lifecycle calls, and manages deduplication and stabilization.

ADO enrichment (PR lineage, approvers, work items) is deferred to Phase 2.

---

## 3. Scope & Constraints

- **Prod-only.** Dev and nonprod do not require change requests. The `env=prod` label selector is a hard gate — applied server-side on the Akuity list call.
- **Git-initiated syncs only.** Auto-sync is disabled on all prod Applications. Self-heal/drift-correction events (same revision re-applied) are suppressed — detected by `syncResult.revision == last applied revision` and ignored without logging.
- **~500 prod Applications** across East US and WUS3, all accessible via the Akuity cloud API.
- **1:1 app-to-rendered-repo relationship.** No fan-out; one commit to one repo maps to one app. CR granularity is one CR per sync operation.

---

## 4. Event Model & State Transition Detection

The bridge polls once per 15s cycle using a single list call and diffs each app's `operationState` against its last-seen snapshot in Redis.

**State transitions and CR actions:**

| Detected transition | Condition | CR action |
|---|---|---|
| `phase` → `Running` | New `.startedAt` observed | **Create + Start CR** |
| `phase == 'Succeeded'` + health sustained | Stabilization window elapsed (5 min, configurable) | **Close CR — successful** + attach audit |
| `phase in ['Error', 'Failed']` | Sync failed | **Close CR — unsuccessful** + attach audit |
| Close detected, no prior create | Sync completed between polls | **Backfill: retroactive CR** flagged `discovered_closed` |

**Operation identity:**
```
operationKey = sha256(app.metadata.name + operationState.startedAt + operationState.syncResult.revision)
```

Self-heal detection: if `syncResult.revision` matches the last successfully applied revision in `status.history`, the operation is suppressed entirely.

---

## 5. State Tracking & Idempotency

**Redis schema** — keyed by `operationKey`:
```json
{
  "cr_sys_id": "...",
  "state": "pending_close | closed",
  "close_deadline": "2026-07-02T14:35:00Z",
  "sync_result": "Succeeded | Failed | Error",
  "sync_revision": "abc123",
  "superseded": false
}
```

**Per-app last-seen record** — keyed by `app.metadata.name`:
```json
{
  "last_operation_key": "...",
  "last_applied_revision": "abc123"
}
```

**Idempotency rules:**
- All SNOW CR creates include `correlation_id = operationKey`.
- Sync retries within the same operation (same `startedAt`) share one `operationKey` → one CR.
- A new sync of the same revision (manual re-sync) generates a new `operationKey` (new `startedAt`) → new CR.
- Redis state persists across bridge restarts; polling restarts are safe.

**Concurrent syncs on the same app:**
Both CRs are treated as independent. When CR1's stabilization deadline expires and CR2 is active, CR1 closes based on its stored `sync_result` (not current health), with `health_check: "superseded_by_subsequent_sync"` in the audit payload. This is because ArgoCD only exposes the current `operationState`; CR1's state is no longer queryable once CR2 starts.

---

## 6. Success Determination (Health Stabilization)

On `Succeeded` detection, the bridge starts a 5-minute stabilization timer (configurable via env var `STABILIZATION_WINDOW_SECONDS`, default `300`).

On each subsequent poll:
- App remains `Healthy` through the window → close CR successful.
- App goes `Degraded` within the window → close CR unsuccessful immediately.
- A new sync starts (CR2 detected) before deadline → close CR1 on sync result with superseded flag.

The stabilization timer deadline is stored in Redis and checked on each poll cycle. A background `asyncio.Task` drives deadline expiry checks.

---

## 7. Audit Package

**Phase 1 — ArgoCD-sourced JSON** (attached to CR via `attach_audit` call after close):

```json
{
  "operation_key": "sha256...",
  "app_name": "my-app",
  "initiated_by": "firstname.lastname@org.com",
  "sync_revision": "abc1234",
  "started_at": "2026-07-02T14:30:00Z",
  "finished_at": "2026-07-02T14:32:15Z",
  "stabilized_at": "2026-07-02T14:37:15Z",
  "sync_result": "Succeeded",
  "health_outcome": "Healthy",
  "health_check": "stabilization_window",
  "resources_synced": [...],
  "argo_project": "my-tenant",
  "destination_cluster": "wus3",
  "destination_namespace": "my-namespace"
}
```

**Phase 2 — ADO enrichment (deferred):** PR author, approvers, linked work items, image tag changes. Fetched via ADO API using rendered commit SHA as the entry point.

---

## 8. SNOW Client Interface

Four methods mapping to the CR lifecycle. Implemented as a thin async class; stubbed for testing, validated against the live API when credentials are available.

```python
async def create_and_start(app_name, operation_key, ...) -> str:  # returns cr_sys_id
async def close_successful(cr_sys_id: str) -> None:
async def close_unsuccessful(cr_sys_id: str) -> None:
async def attach_audit(cr_sys_id: str, audit_payload: dict) -> None:
```

**Failure handling:** Retry 3× with exponential backoff (~30s total window). On exhaustion: log full payload as structured JSON + emit Datadog alert. No queue, no replay worker.

---

## 9. change-bridge Service

- **Runtime:** Python + uv, FastAPI (`GET /healthz` only), `httpx` (async HTTP), `redis-py`, `structlog` (JSON logs).
- **Deployment:** WUS3 cluster, `snow-bridge-gitops` namespace, single instance (no active-active needed).
- **Secrets:** Akuity API key, SNOW credentials, ADO PAT — all via ESO + Azure Key Vault.
- **Main loop:**
  ```
  every 15s:
    apps = GET /api/v1/.../applications?selector=env=prod
    for each app:
      compare operationState to last-seen (Redis)
      if revision unchanged from last applied → skip (self-heal)
      detect transition (Running / Succeeded / Failed / Error)
      update Redis, call SNOW as needed
    check stabilization deadlines for pending-close records
  ```
- **Concurrency:** Single asyncio event loop; stabilization timer checks run as a background `asyncio.Task`. ADO enrichment calls (Phase 2) use `asyncio.gather` for concurrent per-close fetches.
- **Observability (Datadog via DogStatsD):**
  - `bridge.poll.duration` — time per poll cycle
  - `bridge.apps.polled` — apps processed per cycle
  - `bridge.transitions.detected` (tagged by type: running/succeeded/failed/backfill)
  - `bridge.cr.created`, `bridge.cr.closed` (tagged by result: successful/unsuccessful/superseded)
  - `bridge.snow.errors` (tagged by method)
  - `bridge.akuity.429s` — rate limit backoff events

---

## 10. Polling & Rate Limits

- **Interval:** 15s (configurable via `POLL_INTERVAL_SECONDS`).
- **API call rate:** ~4 list requests/minute to Akuity — negligible.
- **429 handling:** Exponential backoff with jitter; configurable minimum request interval (`MIN_REQUEST_INTERVAL_MS`). Alert on sustained backoff.
- **Akuity rate limits:** TBD — confirm against live instance post-deployment.

---

## 11. Phase 0 Prerequisites

Before any bridge code deploys to WUS3:

1. **In-cluster HA Redis** — Bitnami Redis with Sentinel via Helm, WUS3, `snow-bridge-gitops` namespace.
2. **Key Vault + ESO configuration:**
   - Akuity API key (key exists; needs KV entry + ESO SecretStore wiring)
   - SNOW API credentials
   - ADO PAT (for Phase 2 enrichment; can defer until then)
3. **Namespace creation:** `snow-bridge-gitops` on WUS3.
4. **Akuity API access verification:** Confirm list endpoint response shape includes full `operationState`; confirm rate limit thresholds.

---

## 12. Rollout Plan

1. **Phase 0:** Provision Redis, namespace, Key Vault entries + ESO. Verify Akuity list API response shape. Confirm rate limits.
2. **Phase 1 (MVP):** Bridge polling loop, Redis state tracking, create/start/close/attach-audit against SNOW **test instance**. Validate correlation, idempotency, stabilization window, backfill path, and concurrent-sync handling.
3. **Phase 2:** ADO enrichment at close time (PR author, approvers, work items, image tags). Expand audit JSON.
4. **Phase 3:** Promote to SNOW prod instance; enable Datadog monitors and alerts on bridge health, polling lag, SNOW errors, and Akuity 429s. Write runbook.
5. **Phase 4 (deferred):** Rollback detection and tagging.

---

## 13. Decisions Log

| Decision | Choice | Rationale |
|---|---|---|
| CR granularity | Per-app-sync | 1:1 app-to-repo; no fan-out problem |
| Scope | Prod only (`env=prod`) | Nonprod has no ITIL requirement |
| Drift/self-heal | Suppressed | Git-initiated only; same revision = not a change |
| Polling architecture | One list call/cycle | List returns full operationState; 500 apps in one request |
| Poll interval | 15s | Balance detection latency vs. API load; unknown sync durations |
| State store | In-cluster HA Redis | Stabilization timers must survive pod restarts |
| Language | Python + uv | Team preference |
| Deployment | WUS3, snow-bridge-gitops | Single instance sufficient; Akuity API aggregates both regions |
| Stabilization window | 5 min, configurable | Health after sync ≠ health after deployment |
| Concurrent CRs | Independent | Both tracked; superseded CR closes on sync result |
| Rollbacks | Deferred (Phase 4) | Not required by change management at this time |
| SNOW failure | Log + alert, no queue | Low SNOW downtime frequency; manual fallback acceptable |
| ADO enrichment | Phase 2 | Primary audit need (who clicked sync) is in ArgoCD data |
| Audit attachment | Separate call after close | SNOW API supports separate attach; `cr_sys_id` held in Redis |
