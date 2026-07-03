# Configuration Reference

All configuration is injected via environment variables. Secrets are provided by ESO from Azure Key Vault; non-secret config is set in the Kubernetes Deployment manifest.

---

## Akuity API

| Variable | Required | Default | Description |
|---|---|---|---|
| `AKUITY_BASE_URL` | Yes | — | Base URL for the Akuity API (e.g. `https://akuity.cloud`) |
| `AKUITY_ORG_ID` | Yes | — | Akuity organization ID |
| `AKUITY_INSTANCE_ID` | Yes | — | Akuity ArgoCD instance ID |
| `AKUITY_API_KEY` | Yes | — | API key (injected by ESO from Key Vault) |
| `AKUITY_APP_LABEL_SELECTOR` | No | `env=prod` | Label selector applied server-side to the applications list call |
| `AKUITY_MIN_REQUEST_INTERVAL_MS` | No | `1000` | Minimum ms between Akuity API calls; rate-limit floor |
| `AKUITY_MAX_RETRIES` | No | `3` | Max retry attempts on 5xx or 429 responses |

---

## Polling

| Variable | Required | Default | Description |
|---|---|---|---|
| `POLL_INTERVAL_SECONDS` | No | `15` | How often the main polling loop runs (seconds) |
| `STABILIZATION_WINDOW_SECONDS` | No | `300` | How long to wait after `Succeeded` before closing CR as successful (seconds) |

---

## Redis

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_URL` | Yes | — | Redis connection URL (e.g. `redis://redis-sentinel:26379/0`) |
| `REDIS_SENTINEL_MASTER` | No | `mymaster` | Sentinel master name (if using Redis Sentinel) |
| `REDIS_KEY_TTL_SECONDS` | No | `86400` | TTL for operationKey records in Redis (default 24h) |

---

## ServiceNow

| Variable | Required | Default | Description |
|---|---|---|---|
| `SNOW_BASE_URL` | Yes | — | Base URL for the ServiceNow instance (e.g. `https://org.service-now.com`) |
| `SNOW_API_KEY` | Yes | — | API credentials (injected by ESO from Key Vault) |
| `SNOW_MAX_RETRIES` | No | `3` | Max retry attempts on SNOW API failures |
| `SNOW_RETRY_BACKOFF_BASE_MS` | No | `2000` | Base backoff interval for SNOW retries (ms, doubles each attempt) |
| `SNOW_TIMEOUT_SECONDS` | No | `30` | HTTP timeout for SNOW API calls |

---

## Azure DevOps (Phase 2)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ADO_ORG` | Phase 2 | — | ADO organization name |
| `ADO_PAT` | Phase 2 | — | Personal Access Token (injected by ESO from Key Vault) |
| `ADO_TIMEOUT_SECONDS` | No | `15` | HTTP timeout for ADO API calls |

---

## Observability

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATADOG_STATSD_HOST` | No | `localhost` | DogStatsD agent host |
| `DATADOG_STATSD_PORT` | No | `8125` | DogStatsD agent port |
| `SERVICE_NAME` | No | `change-bridge` | Service name tag on all metrics and logs |
| `ENV` | No | `prod` | Environment tag on all metrics and logs |

---

## Open Questions

1. **`AKUITY_BASE_URL` format** — What is the exact base URL for the Akuity cloud API? Is it consistent across orgs (e.g. `https://akuity.cloud`) or org-specific (e.g. `https://{org}.akuity.cloud`)?

2. **`SNOW_API_KEY` vs client credentials** — Does the SNOW CR API use a simple API key, basic auth (username + password), or OAuth client credentials? The variable above assumes a single API key; adjust if the auth model differs.

3. **`REDIS_URL` format** — Confirm the Sentinel connection string format expected by the in-cluster Redis deployment. If Sentinel is not used (standalone HA), a standard `redis://host:6379` URL applies.

4. **`AKUITY_INSTANCE_ID`** — Confirm the instance ID for the production Akuity instance. This is distinct from the org ID and appears in the API path.

5. **`STABILIZATION_WINDOW_SECONDS` per-app override** — Should individual apps or ArgoCD projects be able to override the stabilization window (e.g., via an ArgoCD Application annotation)? Currently a single global value.
