# 02 — Source Plane

**Parent:** ARCH-2026-CI-ARTIFACT-001 §4.1, Principle P6 (everything declarative, including the pipeline)
**Feature prefix:** `SRC`

---

## Executive Summary

The Source Plane defines what lives in Git and how it is structured: application repositories holding code plus schema-validated *config source*, and a platform repository holding the constitution — pipeline templates, promotion topology, policy, and bootstrap. The deliberate omissions are as important as the contents: no environment branches, no human-maintained rendered-output branches, no per-app pipeline logic. This document specifies repository archetypes, the typed configuration schema that becomes the tenant-facing API of the whole platform, branch/merge policy, and the scaffolding automation that stamps out conformant repos. The config schema is the plane's contract-freeze item — every render, validation, and review feature downstream consumes it.

**Why it matters to the business:** a typed, versioned config schema turns onboarding from a consulting engagement into a form-fill, and turns "can we safely let 100 teams self-serve?" from a staffing question into a validation rule.

---

## Principle Breakdown

### P6 — Everything is declarative, including the pipeline
- App repos contain zero imperative pipeline logic. A thin bootstrap file pins a versioned pipeline template and supplies typed parameters; all behavior lives in the platform repo and is released like software.
- The promotion topology, policy bundles, and even the platform's own deployment definitions are files in the platform repo, flowing through the same review → render → publish → promote lifecycle as tenant workloads.

### Design tenets
1. **Code and config source co-located.** One PR changes app code and its deployment intent atomically; one CI run yields one coherent bundle. Cross-repo choreography (app repo triggers config repo triggers pipeline) is a failure amplifier and is excluded.
2. **Config source is typed, not templated.** Tenants author a structured document (validated against a published JSON Schema / CUE definition) — replicas, resources, endpoints, feature flags — not raw manifests or free-form values files. The platform's render toolchain maps typed config → manifests. This is what makes org-wide invariants enforceable pre-merge and makes AI/agent-authored changes safely reviewable.
3. **Trunk-based; environments are not branches.** `main` is the only long-lived branch. Environment differentiation happens through declared render inputs (environment-class sections in config source), never through branch divergence.
4. **The platform repo is the constitution.** Changes to pipeline templates, schemas, or policy carry a mandatory impact report: CI re-renders a sample corpus of tenant configs against the proposed change and posts the fleet-wide diff to the PR (dependency of Doc 08).

## Repository Archetypes

| Repo | Contents | Owner | Notes |
|---|---|---|---|
| App repo (per service) | `src/`, `deploy/config.yaml` (typed), `deploy/base/` optional raw fragments (escape hatch, policy-gated), pipeline bootstrap pin | Tenant team | Scaffolded; conformance checked in CI |
| Platform repo | Pipeline templates, render toolchain pins, config schemas (versioned), policy bundles, promotion topology templates, bootstrap manifests | Platform team | Protected; changes require impact report |
| Hydration mirror (Doc 08) | Machine-written rendered projections | Machinery only | Read-only to humans; a view, never a source |

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 0 | M0–M2 | Repo archetype ADR; branch protection & CODEOWNERS baseline; platform repo bootstrapped |
| 0–1 | M2–M5 | Config schema v1 authored and frozen (contract); validation action available to CI |
| 1 | M4–M8 | Scaffolding generator GA (template-driven repo creation with delta re-application for template upgrades); escape-hatch policy for raw fragments |
| 2 | M9–M14 | Fleet impact-report automation for platform-repo PRs; schema v1.x extension process |
| 3 | M18+ | Schema-driven onboarding portal integration (pairs with Doc 09 self-service) |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-SRC-01 | Repository archetype & branch policy | ADR + enforced settings: trunk-based, protections, CODEOWNERS, required checks; explicit prohibition of env branches. | All new repos conform automatically; policy documented and enforced via SCM API | — |
| FEAT-SRC-02 | Typed configuration schema v1 | Author the tenant-facing config schema (JSON Schema or CUE): workload shape, env-class sections, extension points; versioning rules. | Schema published & frozen; validation library callable from CI and locally | — |
| FEAT-SRC-03 | Config validation gate | Pre-merge CI check validating config source against schema + org invariants; actionable error output. | Non-conformant config cannot merge; median fix-time measured < 1 review cycle | SRC-02 |
| FEAT-SRC-04 | Repo scaffolding & template upgrade tooling | Generator producing conformant app repos from the archetype; supports re-running against existing repos to apply template deltas without clobbering tenant edits. | New service repo in < 10 min; template upgrade PRs raised automatically fleet-wide | SRC-01, SRC-02 |
| FEAT-SRC-05 | Platform repo structure & governance | Layout, ownership, review rules for templates/schemas/policy/topology; release process for platform-repo artifacts (they version and publish like software). | Platform changes ship as versioned releases consumable by pipeline pins | SRC-01 |
| FEAT-SRC-06 | Fleet impact report for platform changes | On platform-repo PRs, re-render a representative tenant corpus against the change; post aggregate diff/summary to the PR. | No pipeline-template or schema change merges blind; report SLA < 15 min | SRC-05, BLD-03, REV-01 |
| FEAT-SRC-07 | Raw-fragment escape hatch policy | Define the narrow, policy-gated path for tenants needing manifests outside the schema; auto-flag for platform review; sunset tracking. | Escape-hatch usage inventoried and trending down; zero un-reviewed fragments | SRC-02, GOV-02 |

## Risks
- **Schema too rigid → escape-hatch sprawl**: mitigate with SRC-07 telemetry and a fast schema-extension lane (target: 2-week turnaround for legitimate gaps).
- **Template upgrades stall across fleet**: SRC-04 delta automation plus GOV adoption gates keep drift bounded.

## References
- Cloudogu GitOps Patterns — repo structure patterns (config split, repo-per-app trade-offs): https://github.com/cloudogu/gitops-patterns
- CUE language (typed configuration): https://cuelang.org/docs/
- JSON Schema specification: https://json-schema.org/specification
- Trunk-Based Development: https://trunkbaseddevelopment.com/
- Copier (template-with-updates scaffolding model): https://copier.readthedocs.io/
- Backstage Software Templates (scaffolding prior art): https://backstage.io/docs/features/software-templates/
- Team Topologies (platform-as-product framing for the platform repo): https://teamtopologies.com/key-concepts
