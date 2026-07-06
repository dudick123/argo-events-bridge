# kyverno-policies

Platform baseline Kyverno policy catalog — PRD-2026-KYVERNO-POLICY-001, story KYV-001-3.

**Status: audit mode only.** Every policy ships with `validationFailureAction: Audit`.
Promotion to Enforce happens per-wave, per-environment (dev → nonprod → prod) under
Phase 3 of the PRD — never by editing this repo ad hoc.

## Catalog (22 policies)

| Category | Policies | Enforcement wave |
|---|---|---|
| security-isolation | privileged, host namespaces, privilege escalation, non-root, RO rootfs, capabilities, seccomp (7) | 1 |
| resource-governance | requests/limits, PDB required, replica cap (3) | 1 |
| image-supply-chain | no `:latest`, approved registries (2) / signature verification (1) | 1 / 4 |
| networking | LB restriction (1) / netpol required, wildcard egress (2) | 2 / 3 |
| secrets-config | no raw Secrets, credential-shaped ConfigMap keys (2) | 1 |
| gitops-hygiene | ownership labels, ArgoCD tracking, sync-wave on Jobs, AppProject scope (4) | 1 |

## Before merge — human review checklist (KYV-001-4)

These are agent-generated drafts. Items requiring human decisions before merge:

- [ ] Replace `platform.example.com/*` label/annotation keys with the real platform label schema (align with quota dashboards + Copier onboarding templates)
- [ ] Replace placeholder ACR hostnames in `restrict-image-registries`
- [ ] Replace Cosign public key placeholder in `verify-image-signatures` (Wave 4 stub)
- [ ] Confirm system-namespace exclusion list matches actual cluster namespaces (repeated per-policy since YAML anchors don't cross document boundaries)
- [ ] Confirm ArgoCD tracking method (label vs. annotation) against Akuity instance config for `require-argocd-tracking`
- [ ] Align `limit-replica-count` cap with tenant tier framework (flat 20 is a placeholder)
- [ ] Validate mutation/validation webhook ordering for `require-requests-limits` vs. HPA injection in dev
- [ ] Run `kyverno test` / CLI apply against representative tenant manifests in CI (kubeconform-style gate, matching PRD-2026-CI-RENDER-001 patterns)

## Known design notes

- `require-pdb-for-multireplica` and `require-network-policy` use `apiCall` context (cross-resource checks) — heavier than pattern checks; validated fine for audit/background mode, revisit admission latency before Enforce.
- `disallow-raw-secrets` excludes ESO-owned Secrets, SA tokens, Helm release storage, and TLS type; expect the exclusion list to grow from Phase 1 audit data.
- The original "block cross-namespace ConfigMap/Secret mounts" concept from the PRD was dropped: Kubernetes pods can only mount ConfigMaps/Secrets from their own namespace, so the policy would be a no-op. Replaced with the credential-shaped-ConfigMap heuristic.

## Repo layout

```
policies/<category>/policies.yaml   # 22 ClusterPolicies, all Audit mode
docs/<category>.md                  # per-policy documentation (purpose, compliance, exceptions)
tests/<category>/<policy>/          # Chainsaw test suite per policy
kustomization.yaml                  # ArgoCD Application sync target
```

## Running the Chainsaw tests

Prerequisites: a kind (or other disposable) cluster with Kyverno installed, plus the
ArgoCD AppProject CRD (needed by the restrict-appproject-scope test):

```
kind create cluster --name kyverno-policy-test
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-cd/master/manifests/crds/appproject-crd.yaml
chainsaw test tests/
```

Test pattern: each suite applies the category policy file, patches only the policy
under test to Enforce (siblings stay Audit so they can't interfere), asserts the
policy reaches Ready, then verifies the good fixture admits and the bad fixture is
denied. Two intentional deviations:

- `verify-image-signatures` — install-only (full verification needs signed test
  images + the real platform Cosign key; Wave 4).
- `require-network-policy` — the test deterministically documents that this policy
  CANNOT be enforced at admission (a new namespace can never already contain a
  NetworkPolicy, so Enforce would deny every tenant namespace creation). Safe in
  Audit/background only; must be redesigned (background-only reporting or a
  generate-based default-deny) before Wave 3. See docs/networking.md.

## CI pipeline

`azure-pipelines.yml` gates every PR in two stages:

1. **Static validation (fast):** yamllint → kustomize build (ArgoCD sync parity) →
   kubeconform schema validation → **audit-mode guard** (fails any PR that commits
   `Enforce` into the base catalog — Wave promotion happens via environment
   overlays with approval checks, never by editing the base) → metadata check
   (every policy must carry `prd` + `enforcement-wave` annotations and have a
   matching Chainsaw test directory).
2. **Chainsaw e2e (slow, ~10-15 min):** kind cluster → Kyverno (pinned chart) →
   prerequisite CRDs (ArgoCD AppProject + a CI-only CiliumNetworkPolicy stub from
   `ci/crds/`) → `chainsaw test tests/` with `parallel: 1` (ClusterPolicies are
   cluster-scoped; parallel Enforce-patching would collide) → JUnit results
   published to the ADO run.

Version pins (Kyverno chart, Chainsaw, kind node image) live at the top of the
pipeline as variables — bump deliberately, and keep the kind node image within
the platform's AKS version skew policy.
