# Skill 7 — AKS Upgrade Preflight Analyzer

**Purpose:** Answer "is it safe to start this upgrade" — deprecated API usage, PDB blockers, add-on/CRD compatibility, node pool constraints — the judgment step that complements your upgrade automation.

## Step-by-step

### 1. Scope the skill
- In scope: version-jump risk assessment, deprecated API detection in manifests, PDB/drain blocker analysis, component compatibility matrix reasoning, preflight checklist generation, go/no-go recommendation framing.
- Out of scope: executing the upgrade (the documented Terraform process owns that), post-upgrade incident debugging, cluster creation.
- Primary users: platform engineers planning upgrade windows.

### 2. Gather ground truth
- Your documented upgrade process itself — the skill should know the mechanism (single `kubernetes_version` variable, serial parallelism, per-resource timeouts, blue-green considerations) so its preflight advice matches how upgrades actually run.
- The platform component inventory with version-compatibility sensitivity: CNI, ESO, Kyverno, ArgoCD agent, gateway, observability agents — for each, where to find its supported-Kubernetes-versions statement.
- Where rendered tenant manifests live (the render-to-Git output is your deprecated-API scanning surface — a major advantage; use it).
- Your PDB conventions and known problem tenants (workloads that historically block drains).
- Notes from past upgrades: what broke, what was checked, what should have been checked.

### 3. Draft the skeleton
- SKILL.md: preflight workflow (target version → API deprecation scan plan → component compatibility check → PDB/drain risk review → capacity/quota check → go/no-go summary) → per-check instructions → risk classification rubric → output format (preflight report template).
- `references/`: component compatibility source list, past-upgrade postmortem notes, known-blocker tenant list, deprecated-API reference per version jump.
- Description triggers: "AKS upgrade", "kubernetes version", "upgrade to 1.x", "deprecated API", "PDB blocking", "node pool upgrade", "preflight".

### 4. Encode the checklist with evidence requirements
For each preflight check, specify: what evidence proves it (a scan output, a version statement, a query result), how to obtain it, and what pass/fail looks like. The skill's job is to assemble a *defensible* go/no-go, so every line of the report should cite its evidence or be marked unverified.

### 5. Declare blind spots — versions are the trap
- Kubernetes deprecation schedules and component compatibility matrices change; the skill's references are snapshots. Instruct it to state reference freshness and direct the engineer to verify current matrices for the specific target version rather than asserting compatibility from memory.
- It cannot see cluster state, Azure quotas, or the actual rendered-manifest repo unless given exports — every check specifies its required input.

### 6. Add worked examples
One full preflight from a past upgrade (reconstructed if needed): target version, checks run, one issue found, how it was resolved before proceeding. Plus one "no-go" example so the skill knows recommending delay is a valid outcome.

### 7. Test triggering and outputs
- Negatives: application deployment questions, node sizing/SKU questions outside an upgrade context, Terraform questions unrelated to version bumps.
- Output test: give it a version jump spanning a known API removal plus a manifest set containing one deprecated resource; verify detection and correct severity.

### 8. Maintain per-upgrade
After every real upgrade, feed lessons back: new checks, new known blockers, updated component notes. Make "update preflight skill" a standing item in the upgrade runbook's closeout.

## Definition of done
- [ ] Preflight checks each specify required evidence and pass/fail criteria
- [ ] Report format marks every conclusion as verified or unverified
- [ ] Component inventory lists authoritative compatibility sources, not cached claims
- [ ] Uses rendered-manifest repo as the API scanning surface
- [ ] Upgrade runbook closeout includes skill update step
