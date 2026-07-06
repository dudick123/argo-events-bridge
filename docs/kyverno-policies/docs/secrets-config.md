# Secrets & Config Policies

Category: `secrets-config` · 2 policies · Wave 1 · PRD-2026-KYVERNO-POLICY-001

Platform invariant: **ESO + Azure Key Vault is the exclusive secret delivery mechanism.** Secrets committed to Git (even sealed/encrypted) or created ad hoc break auditability, rotation, and the platform's single source of secret truth. These policies backstop that invariant at admission.

---

## disallow-raw-secrets

**Severity: high · Wave 1 · Test: `tests/secrets-config/disallow-raw-secrets/`**

Denies creation of raw `Secret` objects in tenant namespaces. Secrets must be materialized by ESO from an `ExternalSecret` backed by Azure Key Vault.

**How to comply:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-secrets
spec:
  secretStoreRef:
    name: tenant-keyvault
    kind: SecretStore
  target:
    name: my-app-secrets
  dataFrom:
    - extract:
        key: my-app-credentials
```

**What's excluded (won't be flagged):**
- Secrets owned by an `ExternalSecret` (ESO-materialized — checked via ownerReferences)
- `kubernetes.io/service-account-token` (controller-managed)
- `helm.sh/release.v1` (Helm release storage — system workloads only)
- `kubernetes.io/tls` (cert-manager-issued certificates)

**Expect the exclusion list to grow** during Phase 1 audit — controller-created Secrets we haven't anticipated will surface in the audit data, and that's precisely why this audits before it enforces.

---

## disallow-secret-env-in-plaintext-configmaps

**Severity: medium · Wave 1 · Test: `tests/secrets-config/disallow-secret-env-in-plaintext-configmaps/`**

Heuristic companion to `disallow-raw-secrets`: flags ConfigMaps whose keys look like credentials (`*password*`, `*api_key*`/`*apikey*`, `*client_secret*`). Once raw Secrets are blocked, the path of least resistance becomes "just put it in a ConfigMap" — this catches that workaround.

**How to comply:** Credential values go through ESO, full stop. Rename genuinely non-secret keys that trip the heuristic (e.g. `PASSWORD_POLICY_URL` → `PWD_POLICY_URL`) or request an exception.

**False positives are expected in audit** — the key-pattern list will be tuned from Phase 1 data before any Enforce discussion. This one may reasonably stay Audit-forever as a reporting signal rather than a hard block; that's a Phase 2 readiness call.
