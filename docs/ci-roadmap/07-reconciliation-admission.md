# 07 — Reconciliation & Admission

**Parent:** ARCH-2026-CI-ARTIFACT-001 §4.5
**Feature prefix:** `REC`

---

## Executive Summary

The Reconciliation Plane is deliberately boring: Argo CD Applications source directly from OCI, pinned to the digest the promotion plane sets, and the repo-server's job collapses to "pull a tarball, apply plain YAML." No rendering, no Git checkout of a monorepo, no template execution at sync time — which removes the largest category of sync-time failure modes and materially improves reconciliation performance at fleet scale. The plane's second half is the last and most important trust boundary: **admission-time verification**, where a cluster-side policy engine independently verifies signature identity, SLSA provenance, and attestation freshness on every workload — so a compromised pipeline, registry credential, or even Argo CD instance still cannot run an unattested artifact. ApplicationSets are generated from the promotion topology so the deployment fleet and the promotion graph cannot drift apart. Rollout runs audit-mode fleet-wide in Phase 1, enforce for pilots in Phase 2, enforce-everywhere by Phase 3.

**Why it matters to the business:** admission verification converts supply-chain security from a pipeline property (bypassable) into a cluster property (structural), and OCI-sourced reconciliation cuts the operational surface of the CD tier roughly in half.

---

## Design Detail

### OCI-sourced Applications
- `source.repoURL: oci://<registry>/<org>/bundles/<app>`, `targetRevision` pinned to the digest the promotion step writes. No machine consumer ever resolves a tag.
- Config layer is plain YAML — sync is fetch + apply. Helm lifecycle features (hooks) are intentionally unavailable by design; sync-wave annotations and platform-provided patterns cover ordering needs. This constraint is documented as a tenant-facing rule, not discovered in migration.
- Repo-server sizing, caching, and failure modes simplify: cache key = digest, invalidation = never (immutability).
- **Fleet generation:** ApplicationSets derive from the promotion topology (PRM-08 templates), so a Stage always has exactly one corresponding Application set with matching destination and source path. Drift between "what promotion thinks exists" and "what Argo manages" is structurally excluded.

### Admission verification (trust boundary #2, independent of #1)
- Cluster-side policy engine (Kyverno `verifyImages` or Sigstore Policy Controller class) verifying on Pod admission:
  1. valid signature from allow-listed CI identity (issuer + subject pattern) chained to the org trust root;
  2. SLSA provenance attestation present, subject matches image digest, builder + source repo in approved set;
  3. scan-attestation freshness within namespace-tier policy;
  4. image referenced by digest (tag-based references rejected in enforced tiers).
- Verification policy is the signed artifact from SCT-04, delivered to clusters through the platform's own GitOps flow; verifiers cache verdicts keyed by digest.
- **Independence property:** admission uses its own trust-root distribution and its own policy evaluation — it shares the *policy source* with promotion intake but not the runtime. Tabletop scenario "Argo CD admin credential compromised" must end with malicious workload rejected at admission.

### Failure and degradation behavior
- Registry unreachable ⇒ reconcilers hold last-applied state; alarms fire; no destructive action (contract tested in REG-05).
- Admission verifier unavailable ⇒ fail-closed for enforced prod tiers (with tight availability SLO + surge capacity on the webhook), fail-open-with-alarm for lower tiers during rollout phases; end-state posture ratified by ADR.
- Sync failure taxonomy shrinks to: pull errors, apply conflicts, health timeouts — each with a runbook.

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 1 | M3–M6 | Pilot Applications on OCI sources in dev; sync performance baseline vs. Git-sourced control group |
| 1 | M6–M9 | Admission verification deployed **audit-mode fleet-wide**; violation dashboard; ApplicationSet generation from topology for pilots |
| 2 | M9–M14 | Enforce admission for pilot namespaces; digest-only reference enforcement; independence tabletop executed |
| 2–3 | M14–M22 | Fleet migration of Applications to OCI sources (cohort-based); enforce expansion by tier |
| 3 | M22–M28 | Enforce everywhere; fail-closed posture for prod ratified and load-tested; legacy Git-source paths decommissioned |
| 4 | M30–M36 | Air-gapped/edge cluster admission with relocated trust roots |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-REC-01 | OCI-sourced Application pattern | Application spec pattern for bundle sources (digest-pinned); repo credentials via workload identity; pilot apps syncing from bundles. | Pilot syncs green from OCI; p95 sync time ≤ Git baseline; runbook for pull failures | RB-02, REG-02 |
| FEAT-REC-02 | Degradation behavior implementation & test | Hold-state behavior on registry unavailability; alerting; joint game-day with REG-05. | Registry outage game-day: zero workload disruption, correct alarms | REC-01, REG-05 |
| FEAT-REC-03 | ApplicationSet generation from promotion topology | Generator producing the Application fleet from topology templates; conformance check that every Stage ↔ Application mapping is 1:1. | Topology change propagates to fleet automatically; drift detector reports zero orphans | REC-01, PRM-08 |
| FEAT-REC-04 | Admission verification — audit rollout | Deploy policy engine with signature + provenance + freshness rules in audit mode fleet-wide; violation reporting pipeline. | 100% of admitted workloads evaluated; violation dashboard live; baseline noise triaged | SCT-03, SCT-04 |
| FEAT-REC-05 | Admission verification — enforcement | Tier-based enforce rollout; digest-only reference rule; fail-open/closed posture per tier; webhook availability SLO + surge sizing. | Pilot prod namespaces reject unsigned/unattested workloads; verified in red-team exercise | REC-04, GOV-01 |
| FEAT-REC-06 | Trust-boundary independence validation | Tabletop + technical exercise: compromised CD credentials cannot admit unattested workloads; admission trust root distributed independently of Argo CD. | Exercise report signed off by security; gaps remediated | REC-05, SCT-07 |
| FEAT-REC-07 | Fleet migration off Git-sourced Applications | Cohort-based migration tooling: convert Application sources, verify digest parity between old rendered state and bundle content, cut over. | 100% of Applications OCI-sourced; legacy render path removed from CD tier | REC-01–03 |

## Risks
- **Argo CD OCI-source maturity gaps over the horizon** — graceful degradation documented in the parent doc §10: hydration mirror (Doc 08) can serve as Application source with zero pipeline change; contracts are engine-agnostic.
- **Fail-closed admission availability** — the sharpest operational edge of the whole architecture; mitigate with webhook HA, digest-verdict caching, pre-verification at promotion, and explicit SLO with error budget before prod enforce.
- **Hook-dependent tenant workloads** — inventory during migration (REC-07); provide platform patterns (waves, jobs) and a documented exception path with sunset dates.

## References
- Argo CD OCI sources: https://argo-cd.readthedocs.io/en/latest/user-guide/oci/
- Argo CD ApplicationSets: https://argo-cd.readthedocs.io/en/latest/operator-manual/applicationset/
- Argo CD sync waves & phases: https://argo-cd.readthedocs.io/en/latest/user-guide/sync-waves/
- Kyverno image verification (signatures + attestations): https://kyverno.io/docs/policy-types/cluster-policy/verify-images/
- Sigstore Policy Controller: https://docs.sigstore.dev/policy-controller/overview/
- Kubernetes admission webhooks (failure policy semantics): https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
- slsa-verifier (provenance verification mechanics): https://github.com/slsa-framework/slsa-verifier
- Argo CD Source Hydrator (fallback source pattern): https://argo-cd.readthedocs.io/en/latest/user-guide/source-hydrator/
