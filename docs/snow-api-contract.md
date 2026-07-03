# ServiceNow CR API Contract (Assumed)

This document captures the **assumed** ServiceNow CR API contract based on the existing Azure Pipelines implementation pattern. All endpoints, payload shapes, and field names must be validated against the live SNOW API before Phase 1 ships.

The bridge uses four operations: **create+start**, **close successful**, **close unsuccessful**, and **attach audit**. These map directly to the SNOW CR lifecycle: create → start → close → attach-audit.

---

## Authentication

Assumed: API key passed as a request header.

```
Authorization: Bearer {SNOW_API_KEY}
Content-Type: application/json
```

---

## 1. Create and Start CR

Opens a new change request and immediately moves it to the implementing/in-progress state in a single logical unit (matching the existing Azure Pipelines behavior).

**Request**

```
POST {SNOW_BASE_URL}/api/...
```

```json
{
  "correlation_id": "sha256:abc123...",
  "app_name": "my-app",
  "initiated_by": "firstname.lastname@org.com",
  "sync_revision": "abc1234",
  "started_at": "2026-07-02T14:30:00Z",
  "destination_cluster": "wus3",
  "destination_namespace": "my-namespace",
  "argo_project": "my-tenant",
  "description": "ArgoCD sync initiated by firstname.lastname@org.com for app my-app revision abc1234"
}
```

**Response**

```json
{
  "sys_id": "abc123def456...",
  "number": "CHG0012345",
  "state": "in_progress"
}
```

The `sys_id` is the durable identifier stored in Redis and used for all subsequent calls against this CR.

---

## 2. Close CR — Successful

Called after the stabilization window confirms the app remained `Healthy`.

**Request**

```
PATCH {SNOW_BASE_URL}/api/.../{sys_id}/close
```

```json
{
  "result": "successful",
  "finished_at": "2026-07-02T14:32:15Z",
  "stabilized_at": "2026-07-02T14:37:15Z",
  "close_notes": "Sync succeeded. App remained Healthy through 5-minute stabilization window."
}
```

**Response**

```json
{
  "sys_id": "abc123def456...",
  "state": "closed"
}
```

---

## 3. Close CR — Unsuccessful

Called when sync phase is `Error` or `Failed`, or when health degrades within the stabilization window.

**Request**

```
PATCH {SNOW_BASE_URL}/api/.../{sys_id}/close
```

```json
{
  "result": "unsuccessful",
  "finished_at": "2026-07-02T14:32:15Z",
  "close_notes": "Sync failed. Phase: Error. Message: one or more synchronization tasks are not running."
}
```

**Response**

```json
{
  "sys_id": "abc123def456...",
  "state": "closed"
}
```

---

## 4. Attach Audit Document

Called immediately after close. Attaches the full audit JSON as a file or structured note to the CR.

**Request**

```
POST {SNOW_BASE_URL}/api/.../{sys_id}/audit
```

```json
{
  "operation_key": "sha256:abc123...",
  "app_name": "my-app",
  "initiated_by": "firstname.lastname@org.com",
  "sync_revision": "abc1234",
  "previous_revision": "def5678",
  "started_at": "2026-07-02T14:30:00Z",
  "finished_at": "2026-07-02T14:32:15Z",
  "stabilized_at": "2026-07-02T14:37:15Z",
  "sync_result": "Succeeded",
  "health_outcome": "Healthy",
  "health_check": "stabilization_window",
  "argo_project": "my-tenant",
  "destination_cluster": "wus3",
  "destination_namespace": "my-namespace",
  "resources_synced": [
    {
      "group": "apps",
      "version": "v1",
      "kind": "Deployment",
      "namespace": "my-namespace",
      "name": "my-app",
      "status": "Synced",
      "message": "deployment.apps/my-app configured"
    }
  ]
}
```

**Response**

```json
{
  "sys_id": "abc123def456...",
  "attachment_id": "xyz789..."
}
```

---

## Error Responses

All endpoints are expected to return standard HTTP status codes:

| Status | Meaning | Bridge behavior |
|---|---|---|
| `200` / `201` | Success | Continue |
| `409 Conflict` | Duplicate `correlation_id` | Treat as success; log and continue |
| `4xx` (other) | Client error | Log, alert, do not retry |
| `5xx` | Server error | Retry with exponential backoff (max 3 attempts); then log + alert |
| `429` | Rate limited | Backoff and retry; alert if sustained |

---

## Open Questions

1. **Endpoint paths** — The actual API paths (`/api/...`) are unknown. What are the full endpoint URLs for create, close, and attach? Does the SNOW instance use a custom scoped app API (e.g. `/api/x_org_change/...`) or a standard table API?

2. **Create vs. start** — Are create and start truly a single API call, or does the bridge need to make two sequential calls (POST to create, then PATCH to start)? The Azure Pipelines implementation combines them — clarify whether this is one or two HTTP requests.

3. **Authentication mechanism** — Confirm whether the SNOW CR API uses Bearer token, Basic auth, or OAuth2 client credentials. Update the `SNOW_API_KEY` env var design accordingly.

4. **`correlation_id` field name** — Confirm the exact field name SNOW uses for the idempotency key. If SNOW doesn't support a native correlation ID, document the duplicate-detection behavior expected.

5. **Close endpoint** — Is close a single endpoint with a `result` field (as assumed above), or are successful and unsuccessful close separate endpoints? Confirm the exact field names and accepted values for `result`.

6. **Audit attachment mechanism** — Does SNOW accept the audit payload as a JSON body (as assumed above), or as a file attachment (multipart/form-data)? If file-based, what filename and MIME type are expected?

7. **Required CR fields** — Are there mandatory fields on CR creation beyond what's listed above (e.g., assignment group, category, change type, template ID)? Missing required fields will cause 4xx errors.

8. **CR number vs sys_id** — The `sys_id` is the internal SNOW identifier used for API calls; `number` (e.g. `CHG0012345`) is the human-readable reference. Confirm which is returned on create and which is needed for subsequent calls.
