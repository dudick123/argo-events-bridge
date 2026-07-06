# 06 — Promotion Plane

**Parent:** ARCH-2026-CI-ARTIFACT-001 §4.4
**Feature prefix:** `PRM`

---

## Executive Summary

The Promotion Plane is the layer classic CI/CD never had: a stateful, reconciling controller that owns environment binding. It models delivery as a graph — **Warehouses** subscribe to the registry and mint **Freight** (an immutable snapshot binding image digest + config digest + metadata); **Stages** (dev → nonprod → prod, fanned out per region) declare which upstream verifications a Freight must pass before becoming eligible; **verification** attaches metric-driven analysis to each stage; **gates** carry approvals, change windows, and ITSM integration. Kargo is the reference implementation, but the deliverable is the *pattern*: subscribe → snapshot → verify → gate → advance, with rollback as re-promotion of prior Freight. This plane is the single component that knows "a change to environment X is happening" — which makes it the natural integration point for change management and the source of the deployment ledger. Delivery targets Phase 2, with pilot tenants promoted end-to-end by month 14 and topology templating for fleet self-service in Phase 3.

**Why it matters to the business:** promotion becomes governed, observable, and reversible by construction — change-management evidence is generated as a side effect of delivery rather than assembled after the fact, and "what is deployed, where, and why is it allowed to be there" has a first-class answer.

---

## Design Detail

### Core model
- **Warehouse per app** subscribes to `bundles/<app>` via registry events (REG-03); Freight-creation policy validates the bundle through the shared trust library (SCT-03) **at intake** — unverifiable bundles never become Freight. Promotion intake is trust boundary #1.
- **Freight** binds the bundle root digest plus resolved metadata (source commit, release annotations). Freight is immutable; hotfix paths use explicit approval of specific Freight, not mutation.
- **Stage graph** per app instantiated from a **topology template** owned by the platform (tenant-parameterized: which regions, which approval tiers, verification thresholds). Availability strategy for multi-upstream fan-in (any-of vs. all-of upstream verification) is a template parameter with an org default of all-of for prod.
- **Promotion steps** update the environment pointer consumed by the reconciliation plane (Doc 07): set the target digest for the corresponding Argo CD Application(s), then await health.

### Verification (continuous, stateful)
- Post-promotion analysis per stage: error-rate/saturation/latency queries against the metrics stack, synthetic probe results, and minimum soak time. Verification templates are platform-owned with tenant-tunable thresholds.
- Freight qualifies downstream only on verification pass; failures roll the stage back to prior Freight automatically where policy allows, or hold-and-page otherwise.
- Verification results are recorded on the Freight — the audit answer to "what evidence admitted this release to prod."

### Gates and governance integration
- **Approval gates:** required approvers per stage tier; approvals are recorded, attributable events.
- **Change windows:** calendar-aware policy (freeze periods, business-hours-only for designated tiers).
- **ITSM hook:** promotion-start opens a change record pre-populated with Freight metadata (digests, commit, diff summary link, verification plan); verification-pass closes it; failure/rollback annotates it. One integration point, entire fleet covered.
- **Break-glass:** explicit Freight approval bypassing upstream verification, requiring elevated identity, auto-opening an emergency change record, and alarming (pairs with GOV-05).

### Rollback
- Re-promotion of a previous Freight through the same mechanism — same verification, same audit trail, no special-case machinery. Rollback depth guaranteed by registry retention pinning (REG-06).

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 1 (late) | M7–M9 | Promotion controller deployed (platform-managed); trust-library intake verification proven against pilot bundles |
| 2 | M9–M12 | Pilot apps: Warehouse → Freight → dev/nonprod Stages with metric verification |
| 2 | M12–M16 | Prod stages with approval gates + change windows; ITSM integration live; automated rollback policy for lower tiers |
| 3 | M18–M24 | Topology templating + tenant self-service instantiation; fleet migration off legacy promotion (tag-mutation) paths |
| 3–4 | M24–M32 | Progressive-delivery verification (canary analysis as stage verification); multi-region fan-out patterns hardened |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-PRM-01 | Promotion controller platform deployment | Deploy/operate the promotion controller (HA, RBAC, project-per-tenant isolation), integrated with registry events. | Controller Tier-1 operational; pilot Warehouse minting Freight from real bundles | REG-03 |
| FEAT-PRM-02 | Freight intake verification | Wire trust library into Freight creation: signature/provenance/freshness/policy-report checks; failures quarantine the bundle. | Unverifiable bundle demonstrably cannot become Freight; quarantine flow exercised | SCT-03, REG-07 |
| FEAT-PRM-03 | Stage graph & promotion steps v1 | dev→nonprod→prod stages for pilot apps; promotion step sets Application target digest and awaits health. | End-to-end promotion of a real release with zero manual pointer edits | PRM-01, REC-01 |
| FEAT-PRM-04 | Metric-driven stage verification | Verification templates querying the metrics stack + synthetics; soak times; pass/fail recorded on Freight. | Regression injected in pilot app is caught at nonprod verification and blocked from prod | PRM-03, OBS-01 |
| FEAT-PRM-05 | Approval gates & change windows | Approver policy per stage tier; calendar-aware freeze/window enforcement; attributable approval records. | Prod promotions require and record approval; freeze period blocks promotion in test | PRM-03, GOV-01 |
| FEAT-PRM-06 | ITSM change-lifecycle integration | Promotion events open/annotate/close change records with Freight metadata and verification evidence. | 100% of prod promotions have auto-managed change records; manual change paperwork eliminated for pilot tenants | PRM-04, PRM-05 |
| FEAT-PRM-07 | Automated rollback & break-glass | Policy-driven auto-rollback to prior Freight on verification failure (lower tiers); break-glass approval flow with elevated identity + emergency change record + alarms. | Rollback MTTR < 5 min in game-day; break-glass usage fully audited | PRM-04, GOV-05 |
| FEAT-PRM-08 | Topology templating & self-service | Platform-owned stage-graph templates instantiated per tenant with typed parameters; onboarding integration. | New tenant gets a conformant promotion graph without platform-team hand-editing | PRM-03–06, GOV-03 |
| FEAT-PRM-09 | Progressive delivery verification | Canary/analysis-run integration as stage verification for opted-in tiers. | Pilot app runs canary-gated prod promotion; rollback on canary failure automatic | PRM-04, REC-01 |

## Risks
- **Verification flakiness erodes trust in gates** — invest early in verification-template quality and flake budgets; a gate teams route around is worse than no gate.
- **Controller as new SPOF for change** — same degradation contract as the registry: outage halts change, not runtime; HA + runbooks; manual pointer-set break-glass documented.
- **Ecosystem/vendor drift** — the plane's contracts (bundle in, digest-pointer out, events emitted) are deliberately thin; a controller swap is a Phase-sized project, not a re-architecture.

## References
- Kargo documentation (Warehouses, Freight, Stages, verification): https://docs.kargo.io/
- Kargo promotion steps reference: https://docs.kargo.io/user-guide/reference-docs/promotion-steps/
- Kargo working-with-stages (availability strategies, verification): https://docs.kargo.io/user-guide/how-to-guides/working-with-stages
- Argo Rollouts + AnalysisTemplates (verification machinery): https://argo-rollouts.readthedocs.io/
- Akuity advanced Kargo example: https://github.com/akuity/kargo-advanced
- "Kargo: The Missing GitOps Promotion Layer" (Deutsche Telekom case discussion): https://akuity.io/blog/kargo-gitops-promotion-layer
- ITIL 4 change enablement (change-record lifecycle framing): https://www.axelos.com/certifications/itil-service-management
- DORA research (change failure rate / lead time metrics the plane emits): https://dora.dev/
