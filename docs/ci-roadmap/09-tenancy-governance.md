# 09 — Multi-Tenancy & Governance

**Parent:** ARCH-2026-CI-ARTIFACT-001 §7
**Feature prefix:** `GOV`

---

## Executive Summary

Governance in this architecture is a product contract, not a review board. Tenants supply schema-conformant config source and receive the entire delivery machinery — pipeline, render toolchain, promotion graph, policy — as a managed service with declared extension points (build runtime, render inputs, verification thresholds, approval requirements). Tenants never author pipeline YAML or promotion logic. Policy is layered: non-overridable org invariants, tier-attached tenant policy, and additive-only app policy. Tenant identity, tiering, and entitlements live in a single machine-readable **tenant registry** that every plane consumes, so "who is this tenant and what are they allowed" has one answer everywhere. Critically, the platform's own components ship through the same pipeline and promotion graph as tenant workloads — the no-exemption rule that makes the platform's guarantees credible. Governance foundations (tenant registry, policy layering, break-glass) are Phase 0–1 work because every other plane takes them as input; self-service onboarding is the Phase 3 payoff.

**Why it matters to the business:** this is what makes 100-team scale compatible with a four-person platform team — governance encoded as validation and policy scales with compute, while governance encoded as meetings scales with headcount.

---

## Design Detail

### The tenant contract
- **Tenant provides:** schema-valid config source (Doc 02); choices at declared extension points; ownership metadata (team, on-call, cost center, tier).
- **Platform provides:** pipeline template, render toolchain, promotion topology, verification templates, policy bundles, registries, and the SLOs on all of it.
- **Interface stability:** extension points and schemas version with deprecation windows; contract changes ship with fleet impact reports (SRC-06). The contract is documented as tenant-facing product docs, not tribal knowledge.

### Tenant registry (single source of tenant truth)
- Machine-readable record per tenant: identity, tier (drives quotas, policy set, approval requirements, verification strictness), environments/regions granted, entitlements, lifecycle state (onboarding → active → offboarding).
- Consumers: scaffolding (SRC-04), pipeline authorization (which repos may publish to which bundle paths), promotion topology instantiation (PRM-08), namespace/RBAC provisioning, registry quotas (REG), policy binding, cost attribution (OBS).
- Changes to the registry flow through review like any other declarative change — tenancy is GitOps-managed too.

### Policy layering
| Layer | Examples | Override |
|---|---|---|
| Org invariants | signature + provenance required; no `latest`; digest-only refs in prod; no raw Secrets in bundles; resource requests mandatory | Never |
| Tier policy | resource ceilings, allowed capabilities, egress classes, approval depth, scan-freshness windows | Platform-approved tier change only |
| App policy | stricter-than-tier settings, additional verification | Additive only |

- One policy bundle, three enforcement points: CI pre-check (BLD-05), promotion intake (PRM-02), admission (REC-04/05) — same source, independently evaluated. Policy bundles are versioned, signed artifacts released through the platform's own promotion graph.

### Break-glass (the governed exception)
- Elevated-identity approval path that bypasses specified gates (upstream verification, freshness, change windows) — never signature/provenance verification, which has no bypass.
- Every use: auto-opened emergency change record, alarm to platform + security, mandatory post-hoc review with expiry on any temporary policy relaxation. Break-glass frequency is a tracked health metric; rising usage is a product signal, not a compliance win.

### Platform self-hosting (the no-exemption rule)
- Policy engine, promotion controller, Argo CD, registries' in-cluster components, render toolchains: all built as Release Bundles, all promoted through their own stage graphs with verification. Bootstrap-order dependencies documented; the only exemptions are the minimal bootstrap set, enumerated and reviewed annually.

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 0 | M0–M3 | Tenant registry schema + store v1; org-invariant policy set v1 drafted; tenant contract doc v1 |
| 1 | M3–M9 | Policy layering implemented across the three enforcement points (audit first); tier definitions ratified; break-glass v1 |
| 2 | M9–M16 | Registry-driven provisioning (namespaces, RBAC, quotas, promotion graphs); platform self-hosting for first components |
| 3 | M18–M28 | Self-service onboarding end-to-end (registry entry → repos → pipeline → promotion graph → namespaces, zero platform-team hand-edits); offboarding automation |
| 4 | M30–M36 | Governance analytics: policy-violation trends, break-glass telemetry, contract-change impact scoring |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-GOV-01 | Tenant registry v1 | Schema, storage, and review workflow for tenant identity/tier/entitlements; read APIs for all planes. | Every plane resolves tenant truth from one source; pilot tenants registered | — |
| FEAT-GOV-02 | Policy bundle framework | Versioned, signed policy bundles (org/tier/app layers); release process via platform promotion graph; consumption contract for the three enforcement points. | Same policy version demonstrably evaluated at CI, promotion, and admission; layering precedence tested | SCT-04, SRC-05 |
| FEAT-GOV-03 | Registry-driven provisioning | Controllers/automation materializing tenant registry state: namespaces, RBAC, quotas, registry scopes, promotion graph instantiation. | Tenant tier change propagates to all planes without manual steps; drift detector clean | GOV-01, PRM-08, REG-02 |
| FEAT-GOV-04 | Tenant contract & product documentation | Tenant-facing docs: contract, extension points, tiering, SLOs, deprecation policy; versioned with the platform. | New-tenant comprehension test passes without platform-team walkthrough | GOV-01, SRC-02 |
| FEAT-GOV-05 | Break-glass framework | Elevated-identity emergency path across promotion/admission gates (excluding signature verification); auto change records; alarms; post-hoc review workflow; usage telemetry. | Break-glass exercised in game-day; every use produces complete audit artifact | PRM-07, SCT-04 |
| FEAT-GOV-06 | Platform self-hosting migration | Move platform components onto Release Bundles + their own promotion graphs; enumerate and minimize bootstrap exemptions. | Policy engine and promotion controller ship via their own verified promotion; exemption list ≤ agreed minimum | RB-06, PRM-03, REC-01 |
| FEAT-GOV-07 | Self-service onboarding flow | End-to-end: registry entry triggers scaffolding, pipeline enrollment, promotion graph, namespaces; offboarding reverse path. | New tenant productive (first verified prod-eligible bundle) in < 1 day without platform hand-edits | GOV-03, SRC-04, PRM-08 |

## Risks
- **Governance perceived as friction → shadow paths** — counter with product mindset: measure onboarding time, gate latency, and escape-hatch usage as platform KPIs; make the paved road genuinely fastest.
- **Tenant registry becomes a change bottleneck** — self-service edits with automated validation for low-risk fields; human review reserved for tier/entitlement changes.

## References
- Kubernetes multi-tenancy guidance: https://kubernetes.io/docs/concepts/security/multi-tenancy/
- Kyverno policy management: https://kyverno.io/docs/
- OPA/Gatekeeper (alternative policy substrate): https://open-policy-agent.github.io/gatekeeper/website/docs/
- Team Topologies (platform-as-product): https://teamtopologies.com/key-concepts
- CNCF Platforms White Paper: https://tag-app-delivery.cncf.io/whitepapers/platforms/
- Backstage (tenant/catalog registry prior art): https://backstage.io/docs/features/software-catalog/
- Kargo project/namespace isolation model: https://docs.kargo.io/user-guide/how-to-guides/working-with-projects
