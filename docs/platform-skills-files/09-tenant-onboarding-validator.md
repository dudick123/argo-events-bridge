# Skill 9 — Tenant Onboarding Validator

**Purpose:** Audit a tenant's onboarding state end-to-end — generated repos, provisioning ledger, ArgoCD wiring, ADO configuration — and report what's complete, missing, or drifted, catching partial-provisioning states that scripts miss.

## Step-by-step

### 1. Scope the skill
- In scope: post-provisioning verification, partial-failure diagnosis ("onboarding ran but tenant can't deploy"), delta-provisioning state reasoning, pre-onboarding readiness checks against the sizing/readiness framework.
- Out of scope: executing provisioning (Copier and the automation own that), modifying the ledger, tenant application debugging post-successful-onboarding.
- Primary users: platform engineers running onboardings and triaging onboarding-adjacent tickets.

### 2. Gather ground truth
- The complete "fully onboarded tenant" definition: for each of the four component types (app-gateway, build-repo, config-repo, argocd-app), what artifacts exist where when provisioning succeeded — repo contents, ledger entries, ArgoCD Application specs, ADO project/pipeline/permission state.
- The `provisioning.yaml` ledger schema and the delta-provisioning semantics: what each state means, what legal state transitions look like, what an inconsistent ledger looks like.
- The dependency graph between components: what must exist before what, so the skill can identify the *first* broken link rather than listing every downstream symptom.
- Real partial-failure cases: onboardings that half-completed, what the state looked like, what the fix was.
- The readiness-assessment framework (scoring domains, pass/fail qualifiers) for the pre-onboarding mode.

### 3. Draft the skeleton
- SKILL.md: two modes clearly separated — (A) pre-onboarding readiness review, (B) post-provisioning audit. For mode B: evidence collection list → component-by-component verification in dependency order → ledger consistency check → findings report format.
- `references/`: per-component "complete state" specs, ledger schema doc, readiness framework rubric, partial-failure case notes.
- Description triggers: "onboard tenant", "provisioning", "tenant can't deploy after onboarding", "provisioning.yaml", "new tenant setup", "onboarding checklist", component-type names.

### 4. Encode verification in dependency order
The skill's differentiator over scripts is causal reasoning: given a set of symptoms, walk the dependency graph to the earliest failed component and explain how the downstream symptoms follow. Write the graph explicitly and instruct: report root cause first, downstream effects as consequences, remediation in dependency order.

### 5. Declare blind spots
- The skill audits evidence it's given (repo listings, ledger contents, app specs, ADO screenshots/exports) — specify the exact evidence bundle to collect for a full audit, and instruct the skill to enumerate which checks it could not perform when given a partial bundle. An audit that silently skips checks is worse than none.
- Ledger contents are claims, not proof — the skill cross-checks ledger against actual artifacts and flags disagreement as its highest-priority finding class.

### 6. Add worked examples
One clean audit (all green, showing the full report format) and one real partial failure: the evidence, the dependency walk, root cause, remediation sequence.

### 7. Test triggering and outputs
- Negatives: general ArgoCD sync issues on established tenants (skill #3), Copier template development questions, tenant resource-quota requests.
- Output test: hand it an evidence bundle with one planted inconsistency (ledger says provisioned, artifact missing); verify it's caught and ranked first.

### 8. Maintain with the onboarding system
Any change to the Copier templates or provisioning logic changes the "complete state" definition. Couple them: the onboarding repo's PR checklist includes updating this skill's component specs.

## Definition of done
- [ ] "Complete state" spec exists per component type
- [ ] Dependency graph encoded; reports lead with root cause
- [ ] Ledger-vs-reality cross-check is the top finding class
- [ ] Skill enumerates unperformed checks on partial evidence
- [ ] Coupled to onboarding repo changes via PR checklist
