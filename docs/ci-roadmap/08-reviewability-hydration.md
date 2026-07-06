# 08 — Reviewability & the Hydration Mirror

**Parent:** ARCH-2026-CI-ARTIFACT-001 §6, Principle P5 (humans review intent and diffs; machines handle mechanics)
**Feature prefix:** `REV`

---

## Executive Summary

The strongest objection to registry-as-truth is losing the Git ergonomics of the rendered-manifests pattern: hydrated diffs in review, `git blame` on what's running, code-search across deployed state. This document resolves that objection with two features. First, **pre-merge rendered diffs**: every config-affecting PR shows the exact YAML delta between the proposal and the *currently promoted digest* per environment class — review happens before merge, which is earlier and stronger than reviewing a hydrated branch after merge. Second, an optional **hydration mirror**: a machine-written, read-only Git projection of every promoted digest, existing purely for human diff/blame/search and auditor ergonomics. The mirror is a *view*, never a source — if it disappeared, nothing would stop deploying. This inverts the classic pattern: Git as the human-readable projection of registry truth rather than registry as a cache of Git truth. Pre-merge diffs land in Phase 1 (they gate build-plane GA); the mirror lands in Phase 2 driven by demonstrated demand.

**Why it matters to the business:** review quality is a leading indicator of change failure rate. Making the true blast radius of every change visible at PR time — a one-line values change that expands to 1,000 lines of manifest change is visible *as* 1,000 lines — is the cheapest change-failure reduction available, and it is also the property that makes AI-generated config changes safely governable at scale.

---

## Design Detail

### Pre-merge rendered diff (the primary reviewability mechanism)
1. CI renders the PR's config source with the pinned toolchain (BLD-03).
2. The diff service resolves the currently promoted digest per environment class (from the ledger, OBS-02), pulls its config layer, and computes a **semantic diff** (object-aware: added/removed/changed resources, field-level changes; noise-normalized).
3. A structured summary posts to the PR: per-env-class change counts, high-risk change flags (RBAC, NetworkPolicy, resource limits, replica drops, CRD changes), expandable full diff.
4. Merge gates: large-diff and high-risk-flag thresholds can require additional reviewers (GOV policy input).
5. The same machinery powers the fleet impact report for platform-repo changes (SRC-06) — one diff engine, two consumers.

### Hydration mirror (optional projection)
- On each promotion event, mirror machinery extracts the promoted bundle's config layer and commits it to `environments/<env>/<app>/…` in a dedicated mirror repo, with commit metadata linking digest, Freight, source commit, and change record.
- **Write access: machinery only.** Branch protection rejects human pushes; the repo carries a banner README stating it is a projection.
- Consumers: humans (`git diff`, `blame`, code search), auditors (point-in-time state reconstruction), and — as documented fallback (REC risk register) — Argo CD itself, should OCI sourcing ever need to be abandoned. The fallback path is exercised annually so it stays real.
- Argo CD's native Source Hydrator is the buy-option evaluated against the build-option here; the decision criterion is whether hydration should key off *promotion events* (recommended — the mirror then reflects what is actually deployed, not merely what merged) versus dry-commit events.

### Semantic diff engine requirements
- Object-aware (group/kind/namespace/name keyed), field-path diffs, stable ordering.
- Noise suppression: managed fields, generation counters, cosmetic reordering.
- Risk classifiers pluggable (policy-driven list of sensitive paths).
- Renders to PR comment (summary + collapsible detail) and to a machine-readable report consumed by gates and the ledger.

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 1 | M3–M6 | Semantic diff engine v1; PR diff comments for pilot repos |
| 1 | M6–M9 | Risk classifiers + reviewer-escalation gates; fleet impact report integration (SRC-06) |
| 2 | M9–M14 | Hydration mirror v1 keyed to promotion events; auditor onboarding; fallback-source drill #1 |
| 3 | M18+ | Diff-driven review analytics (which flagged changes correlate with incidents) feeding risk-classifier tuning |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-REV-01 | Semantic diff engine | Object-aware K8s manifest diff library: field-path deltas, noise suppression, stable output, machine-readable report format. | Diff of two bundle config layers renders correct, review-quality output on golden test corpus | RB-02 |
| FEAT-REV-02 | PR rendered-diff integration | Render proposal, resolve promoted digests per env-class, post structured summary + expandable detail to PRs. | 100% of config-affecting PRs in pilot repos carry rendered diffs; reviewer satisfaction survey ≥ target | REV-01, BLD-03, OBS-02 |
| FEAT-REV-03 | Risk classification & review gates | Pluggable sensitive-path classifiers (RBAC, network, resources, CRDs); threshold-driven additional-reviewer requirements. | High-risk changes demonstrably route to required reviewers; classifier list policy-managed | REV-02, GOV-02 |
| FEAT-REV-04 | Hydration mirror service | Promotion-event-driven projection of promoted config layers into a protected mirror repo with full traceability metadata; machinery-only writes. | Every promoted digest reflected in mirror < 5 min; human push rejected; auditors sign off on ergonomics | REV-01, PRM-03, OBS-02 |
| FEAT-REV-05 | Mirror-as-source fallback drill | Documented + annually exercised procedure to point Applications at the mirror if OCI sourcing must be abandoned. | Drill completes with pilot app served from mirror, zero manifest delta vs. bundle | REV-04, REC-01 |

## Risks
- **Diff noise fatigue** — the engine's noise suppression and summary-first presentation are the product; measure signal via reviewer feedback and iterate before scaling.
- **Mirror mistaken for source of truth** — protections + banner + no human write path; onboarding materials explicit; periodic audit that no automation reads the mirror except sanctioned consumers.

## References
- Akuity, "The Rendered Manifests Pattern": https://akuity.io/blog/the-rendered-manifests-pattern
- Argo CD Source Hydrator: https://argo-cd.readthedocs.io/en/latest/user-guide/source-hydrator/
- dyff (semantic YAML diff prior art): https://github.com/homeport/dyff
- kubechecks (PR-time rendered checks prior art): https://github.com/zapier/kubechecks
- DevOps Directive, "The Rendered Manifests Pattern" (trade-off analysis incl. review-before-merge variant): https://devopsdirective.com/posts/2026/01/rendered-manifests-pattern/
- Google Engineering Practices — code review standards (review-quality framing): https://google.github.io/eng-practices/review/
