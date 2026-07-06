# Platform Maturity Assessment — July 2026

**Scope:** Multi-tenant AKS GitOps platform · ~100 tenants · dev / nonprod / prod · 4-person platform team
**Companion artifact:** `platform-maturity-model-2026.svg`

---

## 1. The model

Five levels, applied per dimension. The scoring rule that keeps this honest: **a capability is scored at what is enforced in prod today, not at what the PRD describes.** You have a lot of Level 4 *designs* sitting on Level 2 *reality* — the model has to show that gap or it's marketing.

| Level | Name | Meaning in your context |
|---|---|---|
| 1 | Ad hoc | Tribal knowledge, manual, per-tenant snowflakes |
| 2 | Repeatable | Documented, PRD exists, partially implemented or audit-mode only |
| 3 | Defined | Implemented as the standard path; enforced for new tenants |
| 4 | Managed | Enforced fleet-wide with metrics, exception process, and self-service |
| 5 | Optimizing | Feedback loops drive continuous improvement; platform measures its own value |

## 2. Scores and honest assessment

**Overall: ≈ 2.6 — a strong late-Level-2 / early-Level-3 platform.**

| Dimension | Now | 24-mo target | Assessment |
|---|---|---|---|
| Secrets management | 4.0 | 4.5 | Your most mature capability. ESO + Key Vault as the *exclusive* mechanism is a real Level 4 posture — single path, no exceptions. Remaining gap is rotation observability and break-glass drills. |
| GitOps & CD | 3.5 | 4.5 | Akuity migration complete, Kustomize discipline, render-to-Git with kubeconform and diff gates designed through v0.3.0. Loses half a point because render-to-Git is not yet the fleet-wide enforced path — it's the backbone everything else depends on. |
| Observability & FinOps | 3.0 | 4.0 | Datadog plus tenant dashboards and quota methodology is solid Defined. What's missing is the *platform measuring itself*: adoption, DX, cost-per-tenant. This maps to the weakest CNCF maturity dimension for you — Measurement. |
| Platform ops & upgrades | 3.0 | 3.5 | Node pool upgrade process documented and optimized, blue-green workload identity patterns exist. Still human-driven and Brian-shaped. |
| Ingress & traffic | 2.5 | 4.0 | Mid-migration is the definition of Level 2.5: two stacks (Kong/App Gateway + Envoy Gateway), double the operational surface, ADRs done, security controls PRD'd but keyed to the new stack. Score rises fast only when Kong is *decommissioned*, not when Envoy is "available." |
| Admission policy (Kyverno) | 2.5 | 4.0 | Framework PRD is comprehensive; HPA injection and mutation policies run in prod. But the bulk of the admission framework is audit-mode or pre-rollout. Audit mode is Level 2 no matter how good the policies are. |
| Tenant onboarding & self-service | 2.5 | 4.0 | Copier system with four component types, provisioning ledger, delta logic — genuinely good design, partially implemented. Until a tenant can onboard without a platform engineer in the loop, it's not self-service. |
| Change mgmt & compliance | 2.0 | 3.5 | ServiceNow bridge is a design with a polling model and Redis state — not running. Today, change evidence is manual. |
| Network segmentation / zero trust | 2.0 | 3.5 | PRD-2026-NETPOL-ZT-001 is well-constructed, but ~100 tenants are effectively flat-network today. Highest risk-to-maturity gap on the board. |
| Supply chain security | 2.0 | 3.5 | Cosign/Syft signing in the build PRD, OCI-as-interface vision documented over a 24–36 month horizon. Nothing verifies signatures at admission yet, so the chain of trust terminates at the registry. |
| AI-assisted engineering | 2.0 | 4.0 | Agent rosters, CLAUDE.md specialists, skills under active design. Ahead of most platform teams, but it's individual leverage (yours), not yet institutionalized team workflow. Biggest force multiplier available to a 4-person team. |
| Developer experience / IDP | 1.5 | 3.0 | Backstage evaluated then deferred; VS Code extension exists. Tenants interact with the platform through repos and tickets. This is where a 100-tenant platform usually feels its scaling pain first. |

### The three honest findings

1. **Design velocity is outrunning enforcement velocity.** You have on the order of ten live PRDs against four engineers. The dashboard shows this as a consistent 1.5-point gap between bar and diamond. The risk isn't bad architecture — it's a shelf of excellent unshipped architecture, and PRDs that drift stale before implementation.
2. **Audit-mode is the platform's comfort zone.** Netpol, admission policy, and supply chain all stall at the same place: the politically and operationally hard step of turning enforcement on across 100 tenants. That step is a *program* (comms, exception process, ratchet schedule), not a PR.
3. **Bus factor ≈ 1 on architecture.** The cross-cutting design work concentrates in one person. The agent/skills work is partly a hedge against this — treat it explicitly as one.

## 3. 24-month forecast

### Opportunities

**H2 2026**
- **Kong decommission.** Finishing the Envoy migration collapses two stacks into one, unlocks the ingress security PRD (Imperva mTLS, NSG allowlisting) on a single policy surface, and frees the ops tax you're paying for dual-running. This is the single highest-leverage completion available.
- **Render-to-Git as the enforced path.** Once fleet-wide, it becomes the substrate for AI PR review, kubeconform gating, and the diff-based human-in-the-loop model. Everything downstream gets cheaper.
- **Enforcement ratchet, wave 1.** Kyverno baseline policies audit→enforce for new tenants first, then cohort-by-cohort. New-tenant enforcement is nearly free politically; do it immediately.

**H1 2027**
- **Zero-trust netpol GA.** Default-deny with Cilium bundles per PRD-2026-NETPOL-ZT-001, riding the same ratchet machinery proven on Kyverno. Hubble flow data pre-stages the rollout by showing tenants what would break.
- **Self-service onboarding end-to-end.** Copier + ADO REST + provisioning ledger with no human in the loop. At 100 tenants and growing, this is the difference between the team scaling and the team drowning.
- **ServiceNow bridge live.** Turns GitOps history into compliance evidence automatically — a cheap, high-visibility win with auditors and leadership.

**H2 2027 – mid-2028**
- **Supply chain enforcement.** Kyverno `verifyImages` requiring Cosign signatures in prod; SBOM attestation; first slice of the OCI-promotion-plane architecture. Your 11-document set becomes real in increments, not as a big bang.
- **AI-assisted engineering as team infrastructure.** Skills and agents versioned in Git, wired into ADO (PR review, briefing dashboard, PRD-drift detection). This is how 4 people operate like 8 — and it's your bus-factor mitigation.
- **Hybrid substrate.** NKP/Arc from POC to production pattern, making the platform multi-substrate rather than AKS-shaped.
- **Lightweight IDP.** Probably not full Backstage — a thin portal or scorecard view over the provisioning ledger and Datadog may deliver 80% of the value.

### Challenges

- **The enforcement wall.** Every security workstream converges on the same hard step: flipping enforce across ~100 heterogeneous tenants. Expect exception requests, broken workloads, and escalations. Without a standing exception process with expiry dates, you'll accumulate permanent exceptions — Level 2 with extra steps.
- **WIP overload.** Ten workstreams / four engineers is the top delivery risk. If nothing is explicitly parked, everything ships late. A visible "not now" list is a deliverable.
- **Migration long tail.** The last 15–20% of tenants on Kong will resist for a year if allowed to. Set a decommission date early and publish it; dual-running indefinitely quietly consumes a fractional headcount.
- **Upgrade treadmill.** AKS + Cilium + Envoy Gateway + Kyverno + Akuity each have their own cadence, and Gateway API / Kyverno CRD churn is real over 24 months. Budget recurring capacity for it or it will steal from roadmap work.
- **Policy and exception sprawl.** A successful Kyverno framework breeds policies. Without ownership metadata, tests, and periodic pruning, year-two you is debugging admission latency and contradictory rules.
- **The measurement gap.** You can't currently prove platform value in numbers (onboarding time, deploy frequency, ticket deflection, cost per tenant). In any 2027 budget or headcount conversation, that absence becomes a business risk, not just a maturity score.
- **Key-person risk.** If architecture context stays concentrated, the platform's ceiling is one person's calendar. The specialist agent files help only if the team actually operates them.
- **AI governance.** As agents touch prod-adjacent repos and pipelines, you'll need the same rigor you apply to tenants: least privilege, human diff gates, audit trail. Better to design it in 2026 than retrofit it after an incident.

### Suggested sequencing spine

One thread pulls the most other threads: **render-to-Git enforced → Kong decommissioned → Kyverno ratchet → netpol ratchet → supply chain verify → self-service GA.** Each stage reuses the rollout machinery (comms, cohorts, exception process) built by the previous one. Build that machinery once, deliberately, in the first ratchet — it's the actual product.

---
*Assessment scored against implementation reality as of July 2026. Re-score quarterly; the interesting number is the delta, not the level.*
