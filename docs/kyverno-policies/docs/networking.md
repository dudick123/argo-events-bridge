# Networking Policies

Category: `networking` · 3 policies · Waves 2 and 3 · PRD-2026-KYVERNO-POLICY-001

These policies push tenant traffic through platform-controlled paths (Envoy Gateway for ingress, Cilium egress gateway for egress) and require a default-deny posture in tenant namespaces. All audit from day one; enforcement is dependency-gated.

---

## require-network-policy

**Severity: high · Wave 3 · Test: `tests/networking/require-network-policy/`**

Flags tenant-labeled namespaces containing zero NetworkPolicy or CiliumNetworkPolicy objects. A namespace with no network policy has unrestricted east-west connectivity to every other tenant — the single largest multi-tenant isolation gap.

**How to comply:** Every tenant namespace should carry at least a default-deny baseline (the Copier onboarding template is the right place to stamp this):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes: ["Ingress", "Egress"]
```

**⚠️ Known design constraint (must resolve before Wave 3):** This policy validates at Namespace admission via `apiCall`, but a brand-new namespace can never already contain a NetworkPolicy — so in Enforce mode it would deny creation of *every* tenant namespace. It is safe in Audit/background mode only, where the background scanner re-evaluates existing namespaces. Before Wave 3, redesign as either (a) background-scan-only reporting feeding a separate enforcement mechanism, or (b) a Kyverno `generate` rule that stamps the default-deny policy into new tenant namespaces automatically — option (b) is likely correct but needs a GitOps-drift discussion since generated resources aren't in Git. The Chainsaw test deterministically documents this constraint.

**Presence, not correctness:** This checks that *a* policy exists, not that it's default-deny. A content-level check is a Wave 3 refinement.

---

## restrict-wildcard-egress

**Severity: medium · Wave 3 · Test: `tests/networking/restrict-wildcard-egress/`**

Flags NetworkPolicy egress rules with an empty `to` clause (allow-all egress) unless the resource carries the `platform.example.com/egress-approved: "true"` annotation, which is granted through the exception process. Unbounded egress undermines the egress gateway segmentation work.

**How to comply:** Scope egress rules to specific destinations (namespaceSelector, podSelector, or ipBlock). If your workload genuinely needs broad egress, request approval — the annotation is the auditable record of that approval.

---

## restrict-loadbalancer-services

**Severity: high · Wave 2 · Test: `tests/networking/restrict-loadbalancer-services/`**

Blocks `Service` of `type: LoadBalancer` in tenant namespaces. Tenant-created LBs bypass the platform ingress path entirely — no Imperva fronting, no NSG allow-listing, no mTLS (PRD-2026-INGRESS-SEC-001 controls), and each one costs an Azure public IP.

**How to comply:** Expose services through the platform gateway with an HTTPRoute bound to the shared Envoy Gateway:
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
spec:
  parentRefs:
    - name: platform-gateway
      namespace: envoy-gateway-system
  rules:
    - backendRefs:
        - name: my-app
          port: 80
```

**Wave 2 gate:** Enforcement waits until Envoy Gateway migration coverage crosses the agreed threshold, so no tenant still legitimately on the old ingress path gets stranded.
