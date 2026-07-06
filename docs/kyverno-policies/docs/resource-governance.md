# Resource Governance Policies

Category: `resource-governance` · 3 policies · All Wave 1 · PRD-2026-KYVERNO-POLICY-001

These policies protect shared cluster capacity and make node maintenance (including the AKS upgrade automation) safe. System namespaces are excluded.

---

## require-requests-limits

**Severity: high · Wave 1 · Test: `tests/resource-governance/require-requests-limits/`**

Requires every container to declare CPU and memory **requests** and a memory **limit**. CPU limits are deliberately not required (CPU throttling is usually worse than time-sharing); memory limits are required because memory is incompressible and an unbounded container triggers node-level OOM kills that affect other tenants.

**How to comply:**
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 256Mi
```

**Interaction with HPA injection:** Workloads using the platform's workload-profile annotations get resources injected by mutation, which runs before validation — those workloads pass automatically. This policy is the backstop for workloads that don't opt in. Webhook ordering is validated in dev during Wave 1 promotion.

---

## require-pdb-for-multireplica

**Severity: medium · Wave 1 · Test: `tests/resource-governance/require-pdb-for-multireplica/`**

Requires at least one PodDisruptionBudget in the namespace for any Deployment/StatefulSet with `replicas > 1`. Without a PDB, node drains during cluster upgrades can evict all replicas simultaneously. This directly supports the AKS upgrade automation's PDB preflight — namespaces passing this policy won't stall or surprise the upgrade sequence.

**How to comply:**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: my-app
```

**Implementation note:** This is a cross-resource check using Kyverno `apiCall` context — it verifies a PDB *exists* in the namespace, not that its selector matches the specific workload. A selector-match refinement is possible but costs admission latency; evaluate from Phase 1 audit data whether the looser check is being gamed before tightening.

---

## limit-replica-count

**Severity: medium · Wave 1 · Test: `tests/resource-governance/limit-replica-count/`**

Caps `spec.replicas` at 20 for Deployments/StatefulSets to prevent a single tenant consuming disproportionate shared capacity via manual scaling or misconfigured HPA maxReplicas.

**How to comply:** Stay at or under the cap, or request a tier exception.

**Placeholder warning:** The flat cap of 20 must be aligned with the tenant sizing/tier framework (XS–XL) before Enforce — likely replaced with a tier-annotation-driven threshold so XL tenants aren't constrained by an XS ceiling.
