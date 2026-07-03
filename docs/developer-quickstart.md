# Developer Quick Start

Welcome to **change-bridge** — a Python service that watches production ArgoCD sync operations (via the Akuity API) and drives the ServiceNow change request lifecycle for each one: create → start → close → attach audit.

This guide gets you from a fresh clone to confidently making changes. Read it top to bottom once; after that, the [document map](#document-map) at the end tells you where everything else lives.

---

## 1. The Big Picture (2 minutes)

Every production deployment in our GitOps setup is a **manual ArgoCD sync** — auto-sync is disabled on all prod apps, so a human clicks "Sync" for every change. ITIL change management requires a ServiceNow CR for each of those deployments. This service automates that paperwork.

The core loop is simple:

```text
every 15 seconds:
    GET all prod apps from Akuity (ONE list call — never per-app calls)
    for each app:
        compare current operationState to what we saw last time (Redis)
        if something changed → create / close a CR in ServiceNow
    check stabilization windows (apps that synced recently and are being health-watched)
```

Three rules explain most of the code:

1. **A sync operation is identified by its `operationKey`** — `sha256(app_name + startedAt + revision)`. Same operation = same key = same CR. New sync = new key = new CR.
2. **"Sync succeeded" ≠ "change successful."** After a successful sync, the CR stays open for a 5-minute **stabilization window**. Stay `Healthy` → close successful. Go `Degraded` → close unsuccessful.
3. **The bridge is a strict observer.** It never touches ArgoCD applications. It reads Akuity, writes ServiceNow, and keeps its memory in Redis.

---

## 2. Setup (10 minutes)

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — the only package manager we use (never `pip install`)
- Docker (for local Redis)

### Steps

```bash
git clone <repo-url> && cd argo-events-bridge

# Install all dependencies (runtime + dev) into .venv/
uv sync

# Local Redis for state storage
docker run -d --name bridge-redis -p 6379:6379 redis:7-alpine

# Environment config (defaults point at localhost mocks)
cp .env.example .env
```

### Verify your setup

```bash
make check
```

This runs lint (`ruff check`), type check (`mypy --strict`), and the test suite (`pytest`). All three must pass — if they do, you're ready. This is also exactly what CI runs, so `make check` passing locally means your PR will pass.

### IDE

Point your interpreter at `.venv/bin/python`. For VS Code, the recommended extensions are `charliermarsh.ruff` and `ms-python.mypy-type-checker` with format-on-save enabled. Full IDE setup (including PyCharm) is in [project-context.md](project-context.md#ide-configuration).

---

## 3. Codebase Tour (read the modules in this order)

Everything lives under `src/bridge/`. The modules are small and single-purpose; reading them in this order builds the picture bottom-up:

| Order | Module | What it does | Why read it |
|---|---|---|---|
| 1 | `clients/akuity.py` | Pydantic models for the ArgoCD `Application` shape + the list-call client | Defines the data everything else consumes; `operation_key()` lives here |
| 2 | `state.py` | Redis records: `OperationRecord` (one per sync op) and `AppSnapshot` (last-seen per app) | The bridge's entire memory model in ~130 lines |
| 3 | `transitions.py` | **Pure logic, no I/O.** Diffs current app state against the snapshot and classifies what happened | The heart of the service — start here when debugging "why did/didn't a CR get created" |
| 4 | `lifecycle.py` | Executes CR actions (open, close + attach audit) against SNOW and persists the result | The only place SNOW lifecycle calls happen |
| 5 | `stabilization.py` | Checks pending-close operations each cycle: degraded → fail now; deadline passed → close successful | Small; implements rule 2 above |
| 6 | `poller.py` | Orchestrates a cycle: list → detect → dispatch → stabilize. Contains dispatch, not business logic | Ties everything together |
| 7 | `clients/snow.py` | HTTP client for the four SNOW operations, retry/backoff, log-and-alert on failure | Read when touching SNOW integration |
| 8 | `config.py`, `logging.py`, `metrics.py`, `health.py`, `__main__.py` | Settings, structlog JSON setup, DogStatsD helpers, `/healthz`, entrypoint wiring | Skim — infrastructure, not domain |

### The transition decision table

`transitions.py` implements this table (full version with JSON examples in [akuity-api-examples.md](akuity-api-examples.md)):

| Last seen | Now | Result |
|---|---|---|
| — | new operation, phase `Running` | `SYNC_STARTED` → create + start CR |
| `Running` | `Succeeded` | `SYNC_SUCCEEDED` → start stabilization window |
| `Running` | `Failed` / `Error` | `SYNC_FAILED` → close CR unsuccessful now |
| — | new operation, already terminal | `BACKFILL_*` → sync finished between polls; create retroactive CR (`discovered_closed`) |
| — | new *automated* sync of the already-applied revision | `SELF_HEAL` → suppress entirely (not a change) |

Two subtleties worth internalizing early:

- **Backfill is a first-class path, not an edge case.** A sync can start and finish inside one 15s poll gap, so the bridge may only ever see the terminal state.
- **Supersede:** if a new sync starts while the previous one is still in its stabilization window, the old CR is closed immediately on its *stored* sync result (flagged `superseded_by_subsequent_sync`) — because ArgoCD only keeps the *current* operation's state, the old operation becomes unobservable the moment a new one starts.

### The Redis memory model

Two record types, stored as JSON strings:

```text
opkey:{operationKey}   → OperationRecord: cr_sys_id, state (open|pending_close|closed),
                          close_deadline, sync_result, audit fields   (24h TTL)
app:{app_name}         → AppSnapshot: last_operation_key, last_phase,
                          last_applied_revision                        (no TTL)
pending_close          → set of operationKeys awaiting stabilization  (index)
```

Everything the bridge knows lives in Redis, never in process memory across cycles — a pod restart resumes stabilization windows and correlation intact.

---

## 4. Development Workflow

### Everyday commands

```bash
make check        # lint + typecheck + test — run before every push
make test-unit    # fast feedback loop while developing
make format       # ruff format (also fixes import order)
uv run pytest tests/unit/test_transitions.py -k self_heal   # one test
```

### Making a change

1. Branch off `main`: `feat/<short-description>` or `fix/<short-description>`.
2. **Write the test first.** This project follows TDD — the test defines the expected behavior, then the minimal implementation makes it pass.
3. Run `make check` until green.
4. Commit using Conventional Commits: `feat(transitions): handle Terminating phase`.
5. Open a PR — one review required, squash merge.

### Testing conventions

- `tests/unit/` — fast, isolated. Mirror the source layout: `src/bridge/transitions.py` → `tests/unit/test_transitions.py`.
- `tests/integration/` — full poll cycles through the `Poller` with fakes.
- **Fixtures live in `tests/conftest.py`** — before writing setup code, look there. You get:
  - `state` — a `StateStore` backed by `fakeredis` (no real Redis needed for tests)
  - `snow` — `FakeSnow`, a recording fake satisfying `SnowClientProtocol`; assert on `.creates`, `.closes`, `.audits`
  - `make_app_payload(...)` — factory producing Akuity API payloads for any app state (running, succeeded, failed, self-heal, ...)
- Mock **at boundaries only**: HTTP via `respx`, Redis via `fakeredis`. Never mock `transitions.py` or `audit.py` — test them directly.
- Async tests need no decorator (`asyncio_mode = "auto"` is set) — just write `async def test_...`.
- Coverage target is 90%+ on `src/bridge/`.

A typical integration test reads like a story — set the app state, run a cycle, assert on SNOW calls:

```python
async def test_failed_sync_closes_immediately(akuity, state, snow, metrics):
    poller = make_poller(300, akuity, state, snow, metrics)

    akuity.set_apps(make_app_payload(phase="Running"))
    await poller.run_cycle()

    akuity.set_apps(make_app_payload(phase="Failed", health="Degraded"))
    await poller.run_cycle()

    assert snow.closes[0][1] == "unsuccessful"
```

---

## 5. Coding Conventions (the ones that will actually bite you)

The full list is in [project-context.md](project-context.md#project-conventions); these are the ones reviewers will flag immediately:

- **`mypy --strict` must pass.** Every function fully annotated. No bare `Any` outside API-boundary parsing.
- **Ruff is the formatter and linter** — 99-char lines, import sorting included. Run `make format` and don't argue with it.
- **All logging through structlog**, as structured events, not sentences:

  ```python
  logger.info("cr_created", operation_key=key, app_name=name, cr_sys_id=sys_id)  # yes
  logger.info(f"Created CR {sys_id} for {name}")                                  # no
  print(...)                                                                       # never
  ```

- **Pydantic at every boundary.** External JSON (Akuity, SNOW) is parsed into models with `extra="ignore"` immediately; internal code never does raw dict access on API responses.
- **Dependency injection everywhere.** Components receive their collaborators via `__init__`/arguments — no globals, no singletons. This is why every test can swap in `FakeSnow` or `fakeredis` without patching.
- **`transitions.py` stays pure.** No I/O, no awaits on external systems. If your change needs I/O during detection, the design is wrong — detection classifies, `poller.py` dispatches, `lifecycle.py` acts.
- **uv only.** `uv add <package>` / `uv add --group dev <package>`. The lockfile is committed; CI uses `uv sync --frozen`.
- **Docstrings** (Google style) on all public modules, classes, and functions — say *why* and state constraints, not what the next line does.

---

## 6. Running the Bridge Locally

The bridge needs an Akuity API and a SNOW API to talk to. For local work you have two options:

1. **Mock servers** (planned as `bridge.dev.mocks` — see [local-development.md](local-development.md) for the workflow and its open questions).
2. **Real Akuity, mocked SNOW** — safe read-only mode: real Akuity credentials in `.env` with `SNOW_BASE_URL` still pointing at a mock, so you can watch real transition detection without ever filing a CR.

Run it:

```bash
uv run python -m bridge          # starts poller + /healthz on :8000
curl localhost:8000/healthz      # {"status": "ok"}
```

Inspect what it's thinking:

```bash
docker exec bridge-redis redis-cli keys 'opkey:*'      # tracked operations
docker exec bridge-redis redis-cli smembers pending_close   # ops in stabilization
docker exec bridge-redis redis-cli get 'app:my-app'    # last-seen snapshot
```

---

## 7. Things That Are Deliberately NOT in the Code

Knowing what's out of scope prevents accidental scope creep in PRs:

- **ADO enrichment** (PR author, approvers, work items) — Phase 2. `clients/ado.py` doesn't exist yet on purpose.
- **Rollback detection/tagging** — deferred to Phase 4.
- **A SNOW retry queue** — deliberate decision: retry 3×, then log the full payload + Datadog alert. Don't add a queue.
- **Nonprod support** — this is a prod-only service by governance design. The `env=prod` selector is a hard gate.
- **Webhooks** — polling only. The single list call per 15s is cheap (~4 req/min); don't add per-app polling or webhook receivers.

The SNOW endpoint paths in `clients/snow.py` are **assumed**, pending contract confirmation (see [snow-api-contract.md](snow-api-contract.md) open questions). If you're validating against the real API, that document is what needs updating alongside the constants at the top of `snow.py`.

---

## Document Map

| Document | Read it when |
|---|---|
| [project-context.md](project-context.md) | You want the full conventions, structure, and constraints reference |
| [EVENT-BRIDGE-DESIGN.md](EVENT-BRIDGE-DESIGN.md) | You want the architecture, the decisions log, and *why* things are this way |
| [akuity-api-examples.md](akuity-api-examples.md) | You're touching transition detection — annotated JSON for every app state |
| [snow-api-contract.md](snow-api-contract.md) | You're touching the SNOW client — assumed contract + open questions |
| [config-reference.md](config-reference.md) | You're adding/using an environment variable |
| [local-development.md](local-development.md) | You're setting up the mock-server workflow |
| [phase0-checklist.md](phase0-checklist.md) | You're working on infrastructure prerequisites |
