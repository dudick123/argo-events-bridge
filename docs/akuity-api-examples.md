# Akuity API Response Examples

Reference examples for the Akuity `GET /api/v1/orgs/{org_id}/instances/{instance_id}/applications` endpoint. The bridge diffs `operationState` against last-seen Redis state on each poll cycle to detect transitions.

These examples are based on the upstream ArgoCD `v1alpha1Application` schema. The Akuity response envelope (outer wrapper) must be confirmed against a live instance.

---

## List Applications Request

```
GET /api/v1/orgs/{AKUITY_ORG_ID}/instances/{AKUITY_INSTANCE_ID}/applications?selector=env=prod
Authorization: Bearer {AKUITY_API_KEY}
```

Expected response shape:

```json
{
  "items": [ ...Application objects... ],
  "metadata": {}
}
```

---

## Application States

### 1. No Current Operation (idle app, nothing happening)

```json
{
  "metadata": {
    "name": "my-app",
    "namespace": "argocd",
    "labels": {
      "env": "prod"
    }
  },
  "spec": {
    "project": "my-tenant",
    "source": {
      "repoURL": "https://dev.azure.com/myorg/my-rendered-repo/_git/my-app",
      "targetRevision": "HEAD",
      "path": "."
    },
    "destination": {
      "server": "https://kubernetes.default.svc",
      "namespace": "my-namespace"
    },
    "syncPolicy": null
  },
  "status": {
    "sync": {
      "status": "Synced",
      "revision": "abc1234"
    },
    "health": {
      "status": "Healthy"
    },
    "operationState": null,
    "history": [
      {
        "revision": "abc1234",
        "deployedAt": "2026-07-01T10:00:00Z",
        "id": 41,
        "source": {
          "repoURL": "https://dev.azure.com/myorg/my-rendered-repo/_git/my-app",
          "path": ".",
          "targetRevision": "HEAD"
        }
      }
    ]
  }
}
```

**Bridge behavior:** `operationState` is null. No transition detected. Skip.

---

### 2. Sync Running (transition: create + start CR)

```json
{
  "metadata": {
    "name": "my-app",
    "namespace": "argocd",
    "labels": {
      "env": "prod"
    }
  },
  "spec": {
    "project": "my-tenant",
    "destination": {
      "server": "https://kubernetes.default.svc",
      "namespace": "my-namespace"
    },
    "syncPolicy": null
  },
  "status": {
    "sync": {
      "status": "OutOfSync",
      "revision": "def5678"
    },
    "health": {
      "status": "Progressing"
    },
    "operationState": {
      "operation": {
        "sync": {
          "revision": "def5678",
          "prune": false,
          "syncStrategy": {
            "hook": {}
          }
        },
        "initiatedBy": {
          "username": "firstname.lastname@org.com"
        }
      },
      "phase": "Running",
      "message": "",
      "syncResult": null,
      "startedAt": "2026-07-02T14:30:00Z"
    },
    "history": [
      {
        "revision": "abc1234",
        "deployedAt": "2026-07-01T10:00:00Z",
        "id": 41
      }
    ]
  }
}
```

**Bridge behavior:** New `operationState.startedAt` + `phase == Running`. Compute `operationKey = sha256("my-app" + "2026-07-02T14:30:00Z" + "def5678")`. Call `create_and_start`. Store in Redis.

---

### 3. Sync Succeeded (transition: start stabilization timer)

```json
{
  "status": {
    "sync": {
      "status": "Synced",
      "revision": "def5678"
    },
    "health": {
      "status": "Healthy"
    },
    "operationState": {
      "operation": {
        "sync": {
          "revision": "def5678"
        },
        "initiatedBy": {
          "username": "firstname.lastname@org.com"
        }
      },
      "phase": "Succeeded",
      "message": "successfully synced (all tasks run)",
      "syncResult": {
        "resources": [
          {
            "group": "apps",
            "version": "v1",
            "kind": "Deployment",
            "namespace": "my-namespace",
            "name": "my-app",
            "status": "Synced",
            "message": "deployment.apps/my-app configured",
            "syncPhase": "Sync"
          },
          {
            "group": "",
            "version": "v1",
            "kind": "ConfigMap",
            "namespace": "my-namespace",
            "name": "my-app-config",
            "status": "Synced",
            "message": "configmap/my-app-config unchanged",
            "syncPhase": "Sync"
          }
        ],
        "revision": "def5678",
        "source": {
          "repoURL": "https://dev.azure.com/myorg/my-rendered-repo/_git/my-app",
          "path": ".",
          "targetRevision": "HEAD"
        }
      },
      "startedAt": "2026-07-02T14:30:00Z",
      "finishedAt": "2026-07-02T14:32:15Z"
    },
    "history": [
      {
        "revision": "def5678",
        "deployedAt": "2026-07-02T14:32:15Z",
        "id": 42
      },
      {
        "revision": "abc1234",
        "deployedAt": "2026-07-01T10:00:00Z",
        "id": 41
      }
    ]
  }
}
```

**Bridge behavior:** `phase == Succeeded`. Set Redis `close_deadline = now + STABILIZATION_WINDOW_SECONDS`. Store `sync_result = Succeeded` and full `resources` array. Do NOT close CR yet.

---

### 4. Sync Failed (transition: close CR unsuccessful immediately)

```json
{
  "status": {
    "sync": {
      "status": "OutOfSync",
      "revision": "def5678"
    },
    "health": {
      "status": "Degraded"
    },
    "operationState": {
      "operation": {
        "sync": {
          "revision": "def5678"
        },
        "initiatedBy": {
          "username": "firstname.lastname@org.com"
        }
      },
      "phase": "Failed",
      "message": "one or more synchronization tasks are not running",
      "syncResult": {
        "resources": [
          {
            "group": "apps",
            "version": "v1",
            "kind": "Deployment",
            "namespace": "my-namespace",
            "name": "my-app",
            "status": "SyncFailed",
            "message": "error validating data: ValidationError(Deployment.spec.template.spec.containers[0])",
            "syncPhase": "Sync"
          }
        ],
        "revision": "def5678"
      },
      "startedAt": "2026-07-02T14:30:00Z",
      "finishedAt": "2026-07-02T14:31:45Z"
    }
  }
}
```

**Bridge behavior:** `phase == Failed`. Call `close_unsuccessful` immediately, then `attach_audit`.

---

### 5. Health Degraded During Stabilization Window (transition: close CR unsuccessful)

Sync succeeded, but on a subsequent poll within the stabilization window the app health drops:

```json
{
  "status": {
    "sync": {
      "status": "Synced",
      "revision": "def5678"
    },
    "health": {
      "status": "Degraded"
    },
    "operationState": {
      "phase": "Succeeded",
      "startedAt": "2026-07-02T14:30:00Z",
      "finishedAt": "2026-07-02T14:32:15Z"
    }
  }
}
```

**Bridge behavior:** CR is in `pending_close` state in Redis. `health.status == Degraded` detected within window. Call `close_unsuccessful` immediately with close notes indicating post-sync health degradation.

---

### 6. Self-Heal / Drift Correction (suppressed — not a change)

ArgoCD re-applies the same revision without a commit change. The key indicator is that `syncResult.revision` matches the most recently applied revision in `status.history`.

```json
{
  "status": {
    "operationState": {
      "operation": {
        "sync": {
          "revision": "abc1234"
        },
        "initiatedBy": {
          "username": "system:serviceaccount:argocd:argocd-application-controller"
        }
      },
      "phase": "Running",
      "startedAt": "2026-07-02T15:00:00Z"
    },
    "history": [
      {
        "revision": "abc1234",
        "deployedAt": "2026-07-01T10:00:00Z",
        "id": 41
      }
    ]
  }
}
```

**Bridge behavior:** `syncResult.revision ("abc1234") == history[0].revision ("abc1234")` → self-heal detected. Suppress entirely. No CR created. Note: auto-sync is disabled on all prod apps, so this case should not occur in practice — but the check is a safety net.

---

### 7. Superseded Operation (second sync started before first CR closes)

First poll cycle sees sync A (revision `def5678`) in `pending_close` state. Next poll sees a new sync B:

```json
{
  "status": {
    "operationState": {
      "operation": {
        "sync": {
          "revision": "ghi9012"
        },
        "initiatedBy": {
          "username": "another.user@org.com"
        }
      },
      "phase": "Running",
      "startedAt": "2026-07-02T14:38:00Z",
      "syncResult": null
    }
  }
}
```

**Bridge behavior:** New `startedAt` detected. Compute new `operationKey` for sync B. Before creating CR for B, check Redis for any `pending_close` records for this app. CR for sync A still open — close it based on stored `sync_result: Succeeded` with `health_check: "superseded_by_subsequent_sync"`. Then create+start CR for sync B.

---

## Transition Detection Logic Summary

| Last-seen `phase` | Current `phase` | `revision` changed? | Action |
|---|---|---|---|
| `null` / absent | `Running` | Yes | Create + Start CR |
| `null` / absent | `Succeeded` or `Failed` | Yes | Backfill: retroactive CR, then close |
| `Running` | `Succeeded` | — | Start stabilization timer |
| `Running` | `Failed` / `Error` | — | Close unsuccessful immediately |
| `Succeeded` (pending_close) | `Succeeded` (same revision) | No | Check stabilization deadline |
| Any | `Running` | Yes (new startedAt) | Supersede any pending CR; create + start new CR |
| Any (same revision) | `Running` | No | Self-heal: suppress |

---

## Open Questions

1. **Response envelope** — Does the Akuity list endpoint wrap items in `{"items": [...]}` (ArgoCD format) or a different top-level structure? Confirm by inspecting a live response.

2. **`operationState` when no operation** — Is `operationState` literally `null`, an absent key, or an empty object `{}` when an app is idle? The bridge null-check logic depends on this.

3. **`initiatedBy` for manual UI syncs** — Does `initiatedBy.username` contain the SSO username (e.g. `firstname.lastname@org.com`) or a different identifier (e.g. UPN, email, display name) when a user clicks sync in the Akuity UI? Confirm format for the audit payload.

4. **`initiatedBy` for pipeline-triggered syncs** — If any syncs are triggered programmatically (e.g., via the Akuity API from a pipeline), what does `initiatedBy` contain? Is it a service principal name or a different identity?

5. **Pagination** — Does the Akuity list endpoint paginate at 500 apps, or return all results in a single response? If paginated, what are the pagination parameters and does the label selector work across pages?

6. **`history` depth** — How many entries does `status.history` typically contain? The bridge reads `history[0].revision` for self-heal detection. Confirm history is ordered most-recent-first.

7. **`syncResult` during `Running` phase** — Is `syncResult` always `null` while `phase == Running`, or can it be partially populated? The bridge assumes null during running.

8. **Rate limit headers** — Does the Akuity API return `X-RateLimit-Remaining` or `Retry-After` headers on 429 responses? If so, the bridge can use them for smarter backoff.
