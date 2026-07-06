# 10 — Observability & the Deployment Ledger

**Parent:** ARCH-2026-CI-ARTIFACT-001 §8
**Feature prefix:** `OBS`

---

## Executive Summary

Because every state transition in this architecture is an event on a digest — bundle published, Freight created, promotion started, verification passed, workload admitted — the system naturally emits a **deployment ledger**: a queryable, tamper-evident record joining digest → commit → PR → ticket → promotion history → runtime state. This document specifies the ledger service, the event contracts each plane must emit, the "what changed?" incident-response query surface, DORA metrics derivation from Freight lifecycle timestamps, and the dashboards for platform SLOs and tenant delivery health. The ledger is also load-bearing infrastructure, not just reporting: registry GC (REG-06) pins retention from it, PR diffs (REV-02) resolve promoted digests from it, and the hydration mirror (REV-04) keys off its promotion events. Event contracts freeze in Phase 1; the ledger reaches load-bearing status in Phase 2.

**Why it matters to the business:** "what changed in the 30 minutes before this alert?" becomes a single query instead of an archaeology exercise across pipeline histories — directly attacking MTTR — and delivery metrics (lead time, deployment frequency, change failure rate) become free byproducts of operating rather than a measurement project.

---

## Design Detail

### Event contracts (per plane)
| Producer | Events | Key fields |
|---|---|---|
| Build plane | bundle.published, gate.failed | digest, app, source commit, PR, pipeline run, attestation refs |
| Registry | artifact.pushed, artifact.deleted, replication.completed | digest, path, identity |
| Promotion | freight.created, promotion.started/succeeded/failed, verification.passed/failed, approval.recorded, breakglass.used | freight id, digest, stage, env, actor, change-record id, evidence refs |
| Reconciliation | app.synced, app.degraded, admission.denied | app, digest, cluster, reason |
| Governance | policy.released, tenant.changed | versions, tenant id |

- Events use a common envelope (CloudEvents), carry the digest as the join key, and are delivered to a durable stream with replay. Emitting conformant events is an acceptance criterion on the producing planes' features — this document owns the *contract*; producers own emission.

### The ledger service
- Consumes the stream into a query-optimized store; exposes:
  - **Digest lineage:** everything known about a digest (build, evidence, promotions, current placements).
  - **Environment timeline:** ordered change history per environment/app — the incident-response primitive.
  - **Placement query:** where is digest D running right now; what digest is running in env E.
  - **Delivery metrics:** DORA-class metrics from Freight lifecycle timestamps (lead time = commit→prod-verified; deployment frequency = prod promotions; change failure rate = prod verification failures + rollbacks / promotions; MTTR = failure→restored-Freight-verified).
- Serves machine consumers (GC, diff service, mirror, AI/assistant tooling via a read API) and human consumers (UI + dashboards).
- **Trust posture:** the ledger is convenient truth, not cryptographic truth — the transparency log and registry remain the tamper-evident spine; ledger records carry pointers into both for audit-grade verification.

### Incident-response surface
- "What changed?" query: given env + time window, return promotions, policy releases, platform-component releases, and topology changes in-window, each linking to diff, Freight evidence, and change record.
- Alert enrichment: monitoring integration annotates alerts with the most recent in-window change events for the affected app/env.
- Deployment markers pushed to the metrics/dashboard stack so every graph carries change context.

### Platform SLO observability
- Plane SLOs (pipeline duration, registry availability/pull latency, promotion latency, verification runtime, admission webhook latency/availability) defined and dashboarded; error budgets gate rollout pace of enforcement features (REC-05's prerequisite).

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 1 | M4–M8 | Event envelope + contracts ratified (freeze); durable stream deployed; build/registry events flowing |
| 1–2 | M8–M12 | Ledger service v1: lineage, timeline, placement queries; promotion events integrated |
| 2 | M12–M16 | Load-bearing consumers cut over (GC, diff service, mirror); incident "what changed?" query GA; deployment markers in dashboards |
| 3 | M18–M24 | DORA metrics GA per tenant + platform rollups; alert enrichment; platform SLO error-budget reporting |
| 3–4 | M24–M36 | Read API for AI/assistant tooling; change-risk analytics (which change classes correlate with verification failures) feeding REV-03 classifiers |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-OBS-01 | Event contracts & durable stream | CloudEvents envelope, per-plane event schemas, delivery guarantees, replay/backfill; conformance tests producers must pass. | Contract frozen; build + registry events flowing with replay proven | REG-03 |
| FEAT-OBS-02 | Deployment ledger service v1 | Stream consumer + query store; digest lineage, environment timeline, and placement APIs; audit pointers to transparency log/registry. | GC, diff service, and mirror consume ledger APIs in staging; query p95 < 500ms | OBS-01, PRM-03 |
| FEAT-OBS-03 | Incident-response query surface | "What changed?" API + UI over env/time windows including platform-component and policy changes; monitoring alert enrichment; deployment markers. | Incident game-day: change identified via ledger in < 2 min; markers on all pilot dashboards | OBS-02 |
| FEAT-OBS-04 | Delivery metrics (DORA) derivation | Metric definitions from Freight lifecycle; per-tenant and platform rollups; trend dashboards. | Metrics published for pilot tenants with documented definitions; no manual data entry | OBS-02, PRM-04 |
| FEAT-OBS-05 | Platform SLO dashboards & error budgets | SLO definitions per plane; dashboards; error-budget policy wired to enforcement-rollout gating. | SLOs live for pipeline/registry/promotion/admission; REC-05 consumes budget status | OBS-01 |
| FEAT-OBS-06 | Ledger read API for tooling | Stable read API (and/or MCP-style surface) for assistants, CLIs, and portals: lineage, placement, timeline, metrics. | Internal tooling answers "what's deployed where and why" without direct plane access | OBS-02–04 |

## Risks
- **Ledger drift vs. reality** — reconciliation job comparing ledger placement against live cluster/Argo state; discrepancies alarmed; replayable stream makes rebuild-from-events the recovery path.
- **Event schema churn breaking consumers** — additive-only evolution within a major, consumer-driven contract tests in producer CI.

## References
- CloudEvents specification: https://cloudevents.io/
- DORA metrics research & definitions: https://dora.dev/guides/dora-metrics-four-keys/
- OpenTelemetry (correlation/enrichment substrate): https://opentelemetry.io/docs/
- Sigstore Rekor (tamper-evident spine the ledger points into): https://docs.sigstore.dev/logging/overview/
- Kargo Freight lifecycle (timestamp sources for metrics): https://docs.kargo.io/user-guide/how-to-guides/working-with-freight
- Argo CD notifications (event emission from reconciliation): https://argo-cd.readthedocs.io/en/latest/operator-manual/notifications/
- Google SRE Workbook — SLOs and error budgets: https://sre.google/workbook/implementing-slos/
