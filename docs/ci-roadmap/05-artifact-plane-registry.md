# 05 — Artifact Plane: The Registry as System of Record

**Parent:** ARCH-2026-CI-ARTIFACT-001 §4.3
**Feature prefix:** `REG`

---

## Executive Summary

This architecture promotes the OCI registry from "image storage" to **the contract surface between build and deploy and the system of record for desired state**. That elevation carries requirements a default registry deployment does not meet: full OCI referrers support, enforced tag immutability, promotion-aware retention, geo-replication so clusters pull locally, Tier-0 availability with a defined degradation story, and audit logging as the pull-side ledger. This document specifies the registry capability requirements, the selection/validation process (gated by the bundle conformance suite), namespace and access design, replication topology, and retention machinery. Registry selection and namespace design are Phase 0 items on the program's critical path — everything downstream pushes to or pulls from this plane.

**Why it matters to the business:** consolidating desired state into replicated, content-addressed, access-audited registries gives disaster recovery, multi-region, and (later) edge/air-gapped distribution a single well-understood mechanism — and reduces "where is the thing we deployed?" to infrastructure that already exists in every container estate.

---

## Design Detail

### Capability requirements (registry selection gate)
1. **OCI Distribution v1.1 referrers API** — attestation discovery is native, not bolted on. Validated by the bundle conformance suite (RB-05), not vendor datasheets.
2. **Tag immutability enforcement** registry-side for bundle repositories; digests canonical. Human-alias tags (`prod-current`) live in a separate mutable-alias namespace that no machine consumer resolves.
3. **Fine-grained, identity-federated access**: per-pipeline push scopes; per-consumer-class pull identities (promotion controller, reconcilers, ledger, scanners) — the access log becomes attributable.
4. **Replication** with digest-consistent semantics across regions; pull-through or push-replication per topology below.
5. **Webhook/event stream** on push and tag operations (feeds Warehouses in Doc 06 and the ledger in Doc 10).
6. **Quota and retention APIs** sufficient to implement promotion-aware GC.

### Namespace design
```
<registry>/<org>/
  bundles/<app>/            release bundle roots + config artifacts (immutable)
  images/<app>/             runtime images (immutable)
  platform/                 render toolchains, pipeline tools, base images, policy bundles
  aliases/<app>/            human-facing mutable tags (no machine consumers)
  quarantine/               failed-verification artifacts held for forensics
```

### Replication & availability topology
- **Hub-and-spoke:** CI pushes to a primary regional registry; replication fans out to per-region read replicas; clusters pull only from their local replica.
- **Degradation contract:** registry outage halts *change*, never *runtime* — last-applied state persists in clusters; reconcilers treat unreachable-registry as "hold current state," alarmed but non-destructive. This contract is tested, not asserted (game-day feature below).
- Air-gapped/edge (Phase 4): the same replication mechanism with an export/import (relocation) step — no new distribution machinery required.

### Retention: promotion-aware garbage collection
- **Pinned:** any digest referenced by any environment pointer (live Freight in any Stage), plus N previous promoted digests per environment for rollback depth.
- **TTL:** unpromoted bundles expire aggressively (e.g., 14 days); PR/branch builds shorter.
- **Legal/audit hold:** label-driven exemption path.
- The GC controller consumes promotion state via the ledger (Doc 10) — retention is derived from delivery reality, not guessed from tags.

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 0 | M0–M2 | Requirements ratified; candidate registries run through conformance suite; selection ADR |
| 0 | M2–M3 | Primary registry hardened: namespaces, immutability, identity-federated access, audit logging on |
| 1 | M3–M8 | Event stream integrated (Doc 06/10 consumers); replication to second region; degradation game-day #1 |
| 2 | M9–M16 | Promotion-aware GC live; quarantine workflow; quota per tenant tier |
| 3 | M18–M28 | Full multi-region topology; DR runbook exercised; registry SLO reporting |
| 4 | M30–M36 | Relocation tooling for air-gapped/edge distribution |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-REG-01 | Registry selection & conformance validation | Run candidates through RB-05 suite (referrers, immutability, events, replication semantics); selection ADR with exit criteria. | Registry chosen on evidence; gaps documented with mitigations | RB-05 |
| FEAT-REG-02 | Registry hardening & namespace rollout | Implement namespace design, immutability enforcement, identity-federated push/pull scopes, audit logging. | No static registry creds; push outside scoped path fails; audit log queryable | REG-01, BLD-01 |
| FEAT-REG-03 | Registry event stream integration | Reliable push/tag event delivery to promotion Warehouses and the ledger; replay/backfill capability. | Warehouse detects new bundle < 60s p95; missed-event backfill proven | REG-02 |
| FEAT-REG-04 | Multi-region replication topology | Hub-and-spoke replication; cluster pull locality; digest-consistency verification job. | Clusters pull only regional replica; cross-region digest audit clean | REG-02 |
| FEAT-REG-05 | Degradation contract & game-days | Define and test outage behavior: reconcilers hold-state, alerting, recovery procedure. | Game-day: full primary-registry outage causes zero workload disruption; change-freeze alarms fire | REG-04, REC-02 |
| FEAT-REG-06 | Promotion-aware retention & GC | GC controller pinning promotion-referenced digests + rollback depth; TTL for unpromoted; legal-hold labels. | Storage growth bounded; zero incidents of GC deleting a promotable/rollback digest | REG-03, OBS-02 |
| FEAT-REG-07 | Quarantine & forensics workflow | Failed-verification artifacts moved to quarantine namespace with preserved referrers; access restricted; retention for investigation. | Security team can reconstruct full provenance of any quarantined artifact | REG-02, SCT-03 |

## Risks
- **Referrers support gaps in chosen registry** — RB-04 fallback (attestation-by-convention tags) keeps the program moving; treat as debt with a burn-down date.
- **GC correctness** — the one place immutability can be violated by deletion; mitigate with dry-run mode, deletion budgets, and a mandatory pin-check against live promotion state at delete time.

## References
- OCI Distribution Spec v1.1 (referrers, tag semantics): https://github.com/opencontainers/distribution-spec/blob/main/spec.md
- ORAS artifact management: https://oras.land/docs/
- Harbor (replication, immutability, quotas — reference capability set): https://goharbor.io/docs/
- Azure Container Registry geo-replication (managed-registry reference model): https://learn.microsoft.com/azure/container-registry/container-registry-geo-replication
- Carvel imgpkg copy (relocation for air-gapped): https://carvel.dev/imgpkg/docs/latest/air-gapped-workflow/
- Argo CD OCI repositories & credentials: https://argo-cd.readthedocs.io/en/latest/user-guide/oci/
- Flux OCI artifacts ("GitOps cache" pattern prior art): https://fluxcd.io/flux/cheatsheets/oci-artifacts/
