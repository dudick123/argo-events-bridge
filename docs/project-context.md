# Project Context

## Purpose

The change-bridge is a Python service that automates the ServiceNow Change Request lifecycle for production GitOps deployments. It polls the Akuity ArgoCD API to detect sync operations on production Applications, maps those operations to CR lifecycle events (create → start → close → attach audit), and delivers them to the existing ServiceNow CR API.

Auto-sync is disabled on all production Applications. Every sync is a deliberate, manually-initiated action. The primary audit question is **who clicked sync** — captured directly from `operationState.operation.initiatedBy.username` without requiring external enrichment. ADO enrichment (PR author, approvers, work items) is deferred to Phase 2.

The bridge is a strict observer: it reads ArgoCD state, writes to ServiceNow, and maintains correlation state in Redis. It does not modify ArgoCD Applications or intervene in deployments.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package Manager | uv |
| Async Runtime | asyncio (stdlib) |
| HTTP Client | httpx (async) |
| Configuration | pydantic-settings v2 |
| State Store | Redis (redis-py, in-cluster HA Sentinel) |
| Web Framework | FastAPI (`/healthz` only) |
| Linting & Formatting | Ruff |
| Type Checking | mypy (strict mode) |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Container Base Image | python:3.12-slim (multi-stage build) |
| Kubernetes Manifests | Kustomize (hydrated for ArgoCD) |
| GitOps | ArgoCD (Akuity cloud) |
| Secrets | ESO + Azure Key Vault |
| Observability | Datadog (DogStatsD metrics, structlog JSON log collection) |

---

## Project Structure

```
argo-events-bridge/
├── src/
│   └── bridge/
│       ├── __init__.py
│       ├── __main__.py             # Entry point: starts asyncio event loop
│       ├── config.py               # Pydantic-settings models, env var parsing
│       ├── poller.py               # Main poll loop: list apps, diff operationState
│       ├── transitions.py          # Transition detection logic (Running/Succeeded/Failed)
│       ├── stabilization.py        # Stabilization window timer management
│       ├── state.py                # Redis schema: operationKey records, last-seen app state
│       ├── audit.py                # Assemble audit JSON payload from ArgoCD data
│       ├── health.py               # FastAPI app with /healthz endpoint
│       ├── metrics.py              # DogStatsD metric definitions and helpers
│       ├── logging.py              # structlog configuration, JSON renderer
│       └── clients/
│           ├── __init__.py
│           ├── akuity.py           # Akuity API client (list apps, get events)
│           ├── snow.py             # SNOW CR API client (create_and_start, close, attach)
│           └── ado.py              # ADO API client (Phase 2 — PR enrichment)
├── tests/
│   ├── conftest.py                 # Shared fixtures: Redis mock, HTTP mocks, sample app state
│   ├── unit/
│   │   ├── test_transitions.py     # Transition detection logic
│   │   ├── test_stabilization.py   # Timer deadline logic
│   │   ├── test_state.py           # Redis read/write helpers
│   │   ├── test_audit.py           # Audit JSON assembly
│   │   └── test_config.py          # Env var parsing and validation
│   └── integration/
│       ├── test_poll_cycle.py      # Full poll cycle against mock Akuity + mock SNOW
│       └── test_lifecycle.py       # End-to-end CR lifecycle (create → close → attach)
├── kustomize/
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── externalsecret.yaml     # ESO secret bindings
│   │   └── redis/                  # HA Redis Sentinel manifests
│   └── overlays/
│       └── wus3/                   # Production overlay for WUS3 cluster
│           ├── kustomization.yaml
│           └── configmap-patch.yaml
├── docs/
│   ├── project-context.md          # This file
│   ├── EVENT-BRIDGE-DESIGN.md      # Architecture and design decisions
│   ├── config-reference.md         # All environment variables
│   ├── snow-api-contract.md        # Assumed SNOW API contract (validate before Phase 1)
│   ├── akuity-api-examples.md      # Akuity API response examples and transition logic
│   ├── phase0-checklist.md         # Infrastructure prerequisites checklist
│   └── local-development.md        # Local dev setup and mock server guide
├── Dockerfile                      # Multi-stage production image
├── pyproject.toml                  # Project metadata, dependencies, tool config
├── uv.lock                         # Lockfile (committed)
├── Makefile                        # Common dev commands
└── .env.example                    # All env vars with placeholder values
```

---

## Project Conventions

### Code Style

- **PEP compliance**: All code must comply with PEP 8 (style), PEP 257 (docstrings for public API), and PEP 484 (type annotations).
- **Formatting**: Ruff formatter (`ruff format`) is the single source of truth. Line length: 99 characters.
- **Linting**: Ruff linter (`ruff check`) with rule sets: `E`, `F`, `W`, `I`, `UP`, `S`, `B`, `A`, `C4`, `PT`, `RUF`.
- **Type annotations**: All functions and methods must have complete type annotations. `mypy --strict` must pass with zero errors.
- **Naming**: snake_case for functions, variables, and modules. PascalCase for classes. UPPER_SNAKE_CASE for constants.
- **Imports**: Sorted by Ruff. Standard library first, then third-party, then local. No wildcard imports.
- **Docstrings**: Google style. Required on all public modules, classes, and functions.
- **No `Any` types**: Avoid `Any` except at true integration boundaries (Akuity/SNOW/ADO API response parsing). Prefer explicit types and TypedDicts or pydantic models for external data.

### Dependency Management

- **uv** is the sole package manager. Dependencies are declared in `pyproject.toml`.
- `uv.lock` is committed. All CI and container builds use `uv sync --frozen`.
- Add runtime dependencies: `uv add <package>`. Add dev dependencies: `uv add --group dev <package>`.
- Never use `pip install` directly.

### Architecture Patterns

- **Single asyncio event loop**: One event loop runs the poll loop, stabilization checker, and health server concurrently as `asyncio.Task` objects.
- **Poll loop as the primary driver**: `poller.py` drives everything. One `GET /applications?selector=env=prod` call per 15s cycle; all 500 apps in one response.
- **Stabilization timer as a background task**: `stabilization.py` runs as a parallel `asyncio.Task`, checking Redis deadline records on each tick and closing CRs when windows expire.
- **Separation of concerns**: Transition detection (`transitions.py`), state management (`state.py`), audit assembly (`audit.py`), and external API clients (`clients/`) are strictly decoupled. `poller.py` orchestrates them but contains no business logic itself.
- **Dependency injection**: Pass config, Redis client, HTTP clients, and logger explicitly via function arguments. No global mutable state.
- **Pydantic for all external data**: Akuity API responses, SNOW responses, and config are validated through pydantic models. No raw dict access after the boundary.
- **structlog for all logging**: All log output goes through structlog configured with JSON rendering. No `print()` statements. No stdlib `logging` direct usage.
- **SNOW client behind a protocol**: The SNOW client is defined as a `Protocol` class to allow test doubles without mocking internals.

### Container Development

#### Production Dockerfile

- Multi-stage build: builder stage installs with `uv sync --frozen --no-dev`; final stage copies the virtual environment into `python:3.12-slim`.
- Runs as non-root user (`bridge`, UID 1000).
- Exposes port 8000 (health/`/healthz`).
- Entrypoint: `python -m bridge`.
- Target image size: under 150MB.

#### Dev Containers

The project supports development via [Dev Containers](https://containers.dev/).

- **Configuration**: `.devcontainer/devcontainer.json`.
- **Base image**: Python 3.12 with uv pre-installed.
- **Included tools**: Ruff, mypy, pytest, Redis CLI, kubectl, kustomize.
- **Post-create**: `uv sync` runs automatically.
- **VS Code**: Open project folder; reopen in container when prompted. Requires the "Dev Containers" extension.
- **JetBrains PyCharm**: File → Remote Development → Dev Containers.

### IDE Configuration

#### VS Code

Recommended extensions (`.vscode/extensions.json`):

- `ms-python.python` — Python language support
- `ms-python.mypy-type-checker` — mypy integration
- `charliermarsh.ruff` — Ruff linting and formatting
- `ms-vscode-remote.remote-containers` — Dev Container support

Settings (`.vscode/settings.json`):

- Default formatter: Ruff
- Format on save: enabled
- Organize imports on save: enabled (via Ruff)
- Python interpreter: `.venv/bin/python` (uv-managed)
- mypy: strict mode enabled

#### JetBrains PyCharm

- Set interpreter to `.venv/bin/python`
- Enable Ruff as external formatter (Settings → Tools → External Tools)
- Configure Ruff as file watcher for format-on-save
- Enable mypy plugin with `--strict`
- Mark `src/` as Sources Root, `tests/` as Test Sources Root

### Makefile Commands

```makefile
lint        # ruff check src/ tests/
format      # ruff format src/ tests/
typecheck   # mypy --strict src/
test        # pytest with coverage
test-unit   # pytest tests/unit/
test-int    # pytest tests/integration/ (requires local Redis + mocks)
check       # lint + typecheck + test (CI equivalent)
build       # Build container image
mocks       # Start local Akuity + SNOW mock servers
```

### Testing Strategy

- **Framework**: pytest with pytest-asyncio for async test support.
- **Structure**: `tests/unit/` for fast isolated tests; `tests/integration/` for tests requiring Redis and mock HTTP servers.
- **Coverage**: pytest-cov with a minimum 90% line coverage threshold enforced in CI on `src/bridge/`.
- **TDD workflow**: Write a failing test that defines expected behavior, write minimal implementation to pass, refactor while keeping green.
- **Naming**: Test files mirror source files (`src/bridge/transitions.py` → `tests/unit/test_transitions.py`). Test functions: `test_<behavior_under_test>`.
- **Fixtures**: Shared fixtures in `conftest.py`. Key fixtures: `redis_client` (fakeredis), `akuity_mock` (respx), `snow_mock` (respx), `sample_app_running`, `sample_app_succeeded`, `sample_app_failed`.
- **Mocking**: Mock at boundaries (HTTP responses via `respx`, Redis via `fakeredis`). Never mock transition or audit logic — test it directly.
- **Async tests**: Use `@pytest.mark.asyncio`. All poller, stabilization, and client tests are async.
- **Key test scenarios to cover**:
  - Running → Succeeded → stabilization → close successful
  - Running → Failed → close unsuccessful (immediate)
  - Close detected without prior create (backfill path)
  - Concurrent syncs on same app (superseded close-on-sync-result)
  - Self-heal detection (same revision, suppressed)
  - SNOW API failure → retry → log-and-alert
  - Akuity API 429 → backoff
  - Bridge restart with in-flight operationKey in Redis (recovery)

### Git Workflow

- **Branching**: Feature branches off `main`. Naming: `<type>/<short-description>` (e.g., `feat/snow-client`, `fix/stabilization-timer`).
- **Commits**: Conventional Commits — `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.
- **Pull requests**: All changes via PR with at least one review. PR references the relevant phase or design decision.
- **CI checks on PR**: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`. All must pass.
- **Main branch**: No direct pushes. Squash merge preferred.

---

### Documentation Standards

#### README.md Requirements

The project `README.md` is the primary entry point for developers, tenant teams, and platform engineers. It MUST be comprehensive and kept up to date as the project evolves. Any change that adds, modifies, or removes a user-facing feature, configuration option, metric, environment variable, CLI command, or deployment pattern MUST include a corresponding README update in the same changeset.

**Required sections** (in order):

1. **Project title and summary** — one-paragraph description of what the tool does and the ownership model (platform team vs. tenant team).
2. **Table of contents** — linked section headings for quick navigation.
3. **How It Works** — numbered step-by-step flow from tenant configuration through to observable output (metrics, logs).
4. **Architecture** — ASCII or Mermaid diagram showing the runtime component layout (pod internals, ports, data flow to Prometheus). Include a module structure tree mapping source files to responsibilities, and a bullet list of key design decisions with brief rationale.
5. **Target Configuration** — full YAML example covering every supported target type (HTTP, HTTPS, TCP, internal cluster, custom options). Include a field reference table (field, required, default, description) and a constraints subsection (max targets, min interval, uniqueness, validation behavior on invalid input).
6. **Failure Diagnostics** — table of all failure categories with trigger conditions and suggested actions. Include a heuristic disclaimer note and description of the `diagnostics` object and `suggested_action` field in logs.
7. **Prometheus Metrics** — table of all exposed metrics with name, type, labels, and description. Include example PromQL queries for common use cases (failing targets, firewall blocks, latency percentiles, alerting).
8. **Structured Logging** — example JSON for both successful and failed checks. Describe log fields, the `diagnostics` object structure, and integration with the cluster log pipeline.
9. **Local Development** — prerequisites list, quick-start commands (`uv sync`, `make check`, local run). Makefile command reference table. Dev Container setup for VS Code and JetBrains PyCharm. IDE setup without dev containers (extensions, settings, interpreter configuration).
10. **Python Development Patterns** — dependency management rules (uv only, `uv.lock` committed, `--frozen` in CI). Code style summary (PEP compliance, Ruff, mypy strict, naming, docstrings). Ruff rule set table. Logging patterns (structlog only). Configuration validation patterns (pydantic). Async patterns (bounded concurrency).
11. **Testing** — TDD methodology statement. Commands for running tests. Test directory structure with test counts per file. Testing conventions (naming, fixtures, mocking boundaries, async tests).
12. **Kubernetes Deployment** — Kustomize base manifest inventory table. Default resource profile table. Step-by-step tenant overlay guide with complete YAML examples for `kustomization.yaml` and `configmap-patch.yaml`. Build-and-deploy commands (kustomize build, hydrate, commit). Resource limit override example. Container image build and publish instructions (including multi-stage Dockerfile description). Health probe endpoint table.
13. **Environment Variables** — complete reference table of all environment variables with name, default value, and description.
14. **License** — link to LICENSE file.

**Style rules for README content:**

- Use GitHub-flavored Markdown.
- Prefer tables over long prose for reference material (fields, metrics, commands, env vars).
- Code blocks MUST specify a language (`yaml`, `bash`, `python`, `json`, `promql`).
- YAML and JSON examples MUST be valid and copy-pasteable.
- ASCII diagrams are preferred over images for architecture; they render in all terminals and editors.
- Keep each section self-contained — a reader should be able to jump to any section via the table of contents and understand it without reading prior sections.
- Do not duplicate content from `openspec/` specs or `prd.md` verbatim; the README is the user-facing reference, not the spec.

## Domain Context

- **Akuity-managed ArgoCD**: ArgoCD is hosted as a cloud service by Akuity. The bridge talks to the Akuity API (`/api/v1/orgs/{org}/instances/{instance}/applications`), not a self-hosted ArgoCD. API authentication is via API key.
- **Auto-sync disabled on all prod apps**: Every production sync is a deliberate manual action initiated by a human in the Akuity UI or via the API. `operationState.operation.initiatedBy.username` is the primary audit field.
- **1:1 app-to-rendered-repo**: Each ArgoCD Application has its own dedicated rendered-manifest repository in ADO. One commit to one repo → one app sync. No fan-out.
- **Render-to-Git pattern**: Source code is in ADO source repos. A render pipeline produces hydrated Kubernetes manifests into a separate rendered-manifest repo. ArgoCD syncs the rendered repo. The bridge's enrichment path (Phase 2) traces rendered commit → source PR via the ADO API.
- **ITIL change management**: All production deployments require a ServiceNow CR. The CR lifecycle is: create → start (at sync-running) → close (after health stabilization) → attach audit. The same lifecycle is currently implemented in Azure Pipelines for non-GitOps changes.
- **500 prod apps across East US and WUS3**: All accessible via the Akuity cloud API, which aggregates both regions. The bridge is deployed once on WUS3 and polls all apps in a single list call.
- **env=prod label as the prod gate**: All production ArgoCD Applications carry `env=prod`. The label selector is applied server-side on the Akuity list call. Apps without this label are never seen by the bridge.

---

## Important Constraints

- **One Akuity list call per poll cycle.** Do not poll apps individually for state detection — the list endpoint returns full `operationState` for all apps. Per-app API calls are reserved for the events endpoint at close time (Phase 2 audit enrichment only).
- **Self-heal operations must be suppressed.** If `syncResult.revision` matches the most recently applied revision in `status.history`, the operation is not a change and must be ignored without creating a CR or emitting a Datadog event. In practice this should not occur (auto-sync is disabled), but the check is a required safety net.
- **Concurrent CRs on the same app are independent.** Do not cancel or supersede a pending-close CR when a new sync starts. Instead, close the pending CR based on its stored `sync_result` (not current health) with `health_check: "superseded_by_subsequent_sync"` in the audit payload. This is necessary because ArgoCD only exposes the current `operationState`; once a new sync starts, the prior operation's state is overwritten.
- **Backfill path is first-class.** If a sync completes faster than the 15s poll interval, the bridge may never observe `phase == Running`. The close-without-prior-create path (backfill) must be fully implemented and tested — it is not an edge case.
- **SNOW API failures do not block polling.** On SNOW API failure: retry 3× with exponential backoff (~30s total), then log the full payload as structured JSON and emit a Datadog alert. The polling loop continues regardless. No queue, no replay worker.
- **Rollbacks are out of scope** for Phases 1–3. Do not implement rollback detection or tagging. Deferred to Phase 4.
- **ADO enrichment is Phase 2.** The Phase 1 audit package is sourced entirely from the Akuity API response. No ADO API calls in Phase 1.
- **Redis is required.** In-memory state is not acceptable — stabilization timers and `cr_sys_id` correlation must survive pod restarts.
- **No direct pushes to prod SNOW** during Phase 1–2. All development and validation uses the SNOW test instance.

---

## External Dependencies

| System | Role | Auth | Phase |
|---|---|---|---|
| Akuity cloud API | Source of ArgoCD app state and sync events | API key (ESO → Key Vault) | 1 |
| ServiceNow CR API | Target for CR lifecycle calls and audit attachment | API key or client credentials (ESO → Key Vault) | 1 |
| Redis (in-cluster HA) | Durable state: operationKey records, stabilization timers | No auth (in-cluster) | 1 |
| Datadog agent (WUS3) | Metrics (DogStatsD) and log collection | No auth (local DogStatsD) | 1 |
| Azure Key Vault | Secret store for all credentials | ESO managed identity | 1 |
| Azure DevOps API | PR enrichment: author, approvers, work items | PAT (ESO → Key Vault) | 2 |
