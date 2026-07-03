# Local Development Guide

How to run the change-bridge service locally for development and testing without requiring access to the WUS3 cluster, live Akuity API, or production SNOW.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Docker](https://docs.docker.com/get-docker/) — for running Redis locally
- Python 3.12+

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://dev.azure.com/myorg/argo-events-bridge/_git/argo-events-bridge
cd argo-events-bridge
uv sync
```

### 2. Start local Redis

```bash
docker run -d --name bridge-redis -p 6379:6379 redis:7-alpine
```

Verify it is running:

```bash
docker exec bridge-redis redis-cli ping
# PONG
```

### 3. Configure environment

Copy the example env file and fill in values:

```bash
cp .env.example .env
```

Minimum required values for local development (using mocks):

```bash
# Akuity
AKUITY_BASE_URL=http://localhost:8080
AKUITY_ORG_ID=local-dev
AKUITY_INSTANCE_ID=local-instance
AKUITY_API_KEY=dev-key

# Redis
REDIS_URL=redis://localhost:6379/0

# SNOW
SNOW_BASE_URL=http://localhost:8081
SNOW_API_KEY=dev-key

# Polling (faster for local dev)
POLL_INTERVAL_SECONDS=5
STABILIZATION_WINDOW_SECONDS=30

# Observability
LOG_LEVEL=DEBUG
```

---

## Running the Bridge

```bash
uv run python -m bridge
```

Or via the FastAPI dev server (exposes `/healthz`):

```bash
uv run uvicorn bridge.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/healthz
# {"status": "ok"}
```

---

## Mock Servers

The bridge talks to three external APIs during a poll cycle: Akuity, SNOW, and (Phase 2) ADO. Local development uses lightweight mock servers to simulate API responses without real credentials.

### Starting the mock servers

```bash
uv run python -m bridge.dev.mocks
```

This starts:

- `http://localhost:8080` — Akuity API mock
- `http://localhost:8081` — SNOW CR API mock

### Simulating app states

The Akuity mock exposes a control endpoint to set app state for testing:

```bash
# Trigger a sync-running event for my-app
curl -X POST http://localhost:8080/dev/apps/my-app/state \
  -H "Content-Type: application/json" \
  -d '{"phase": "Running", "revision": "def5678", "initiated_by": "test.user@org.com"}'

# Advance to Succeeded
curl -X POST http://localhost:8080/dev/apps/my-app/state \
  -d '{"phase": "Succeeded", "revision": "def5678"}'

# Simulate health degradation during stabilization window
curl -X POST http://localhost:8080/dev/apps/my-app/health \
  -d '{"status": "Degraded"}'
```

### Inspecting SNOW mock state

```bash
# List all CRs created by the bridge
curl http://localhost:8081/dev/crs
```

---

## Testing

### Unit tests

```bash
uv run pytest tests/unit
```

### Integration tests (requires local Redis and mock servers)

```bash
uv run python -m bridge.dev.mocks &
uv run pytest tests/integration
```

### Running a full lifecycle manually

```bash
# 1. Start mocks and bridge
uv run python -m bridge.dev.mocks &
uv run python -m bridge &

# 2. Trigger a sync
curl -X POST http://localhost:8080/dev/apps/my-app/state \
  -d '{"phase": "Running", "revision": "abc1234", "initiated_by": "test.user@org.com"}'

# 3. Watch bridge logs — should see create+start CR

# 4. Advance to Succeeded
curl -X POST http://localhost:8080/dev/apps/my-app/state \
  -d '{"phase": "Succeeded", "revision": "abc1234"}'

# 5. Wait for stabilization window (30s in local config), then check SNOW mock
curl http://localhost:8081/dev/crs
```

---

## Redis Inspection

Inspect bridge state directly during development:

```bash
# List all operationKey records
docker exec bridge-redis redis-cli keys "opkey:*"

# Inspect a specific operation
docker exec bridge-redis redis-cli hgetall "opkey:sha256:abc123..."

# List all last-seen app records
docker exec bridge-redis redis-cli keys "app:*"
```

---

## Connecting to a Real Akuity Instance (Read-Only)

If you have Akuity API access and want to poll real app state locally (without filing real CRs), set the real Akuity credentials in `.env` and keep the SNOW mock running:

```bash
AKUITY_BASE_URL=https://akuity.cloud   # real value TBD
AKUITY_ORG_ID=your-org-id
AKUITY_INSTANCE_ID=your-instance-id
AKUITY_API_KEY=your-real-key

SNOW_BASE_URL=http://localhost:8081    # still mocked
```

This lets you validate the polling logic and state-diff behavior against real ArgoCD app data without risk of creating CRs in SNOW.

---

## Open Questions

1. **Mock server implementation** — This guide assumes a `bridge.dev.mocks` module exists with control endpoints. This needs to be built as part of the Phase 1 development scaffolding. The interface described above (state injection via `POST /dev/apps/{name}/state`) is a suggested design.

2. **`.env.example` file** — Needs to be created in the repo root with all variables from `docs/config-reference.md` and safe placeholder values.

3. **Test fixture data** — The JSON examples in `docs/akuity-api-examples.md` should be extracted into `tests/fixtures/` once the response envelope format is confirmed (open question 1 in that document).

4. **ADO mock (Phase 2)** — When ADO enrichment is implemented, a third mock server at `localhost:8082` will be needed. Update this guide at that time.

5. **`uv run` entry point** — The `python -m bridge` invocation above assumes a `bridge/__main__.py` entry point. Confirm the actual module structure when the project is scaffolded.
