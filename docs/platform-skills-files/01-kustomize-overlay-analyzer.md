# Skill 1 — Kustomize Overlay Analyzer

**Purpose:** Explain and validate tenant overlay behavior — why a render produced what it did, catch broken patches, detect drift between environment overlays, and review overlay changes before merge.

## Step-by-step

### 1. Scope the skill
- In scope: overlay structure review, patch resolution reasoning, base/overlay drift analysis, render diff interpretation, common anti-patterns.
- Out of scope (state this in the skill): executing renders (CI does that), Helm charts (system workloads only — redirect), live cluster state.
- Primary users: tenants writing overlays; secondary: platform engineers reviewing PRs.

### 2. Gather ground truth
- Your canonical tenant repo layout (directory structure, naming conventions for bases/overlays/components).
- The exact kustomize version and flags your render pipeline uses (patch behavior differs across versions).
- Your platform's allowed/forbidden patterns: e.g., which patch types are preferred (strategic merge vs. JSON6902), whether `components` are permitted, replacement/vars policy.
- The kubeconform/CRD validation config from the render pipeline — the skill should reason with the same schema set CI enforces.
- 3–5 real "why did my render do that" tickets with resolutions.

### 3. Draft the skeleton
- SKILL.md sections: repo layout contract → overlay review checklist → patch resolution reasoning guide → drift analysis workflow → anti-pattern catalog.
- `references/`: full directory-layout spec, patch-type decision guide, kustomize version-specific gotchas.
- Description triggers: "kustomization", "overlay", "patch not applying", "render diff", "why does prod differ from nonprod", plus your tenant repo naming patterns.

### 4. Encode conventions with reasons
For each convention, write the rule *and* the why. Example shape: "Tenants use strategic merge patches for X because JSON6902 index-based paths break when the base changes — recommend conversion when reviewing." The why lets the skill defend the rule when challenged.

### 5. Declare blind spots
- The skill sees files the engineer pastes or attaches — it cannot render. Instruct it: when reasoning depends on rendered output, ask for the CI render artifact or the `kustomize build` output rather than simulating it mentally for complex patch stacks.
- It must never guess base content it hasn't seen — always request the base when analyzing an overlay.

### 6. Add worked examples
Pick incidents that teach reasoning: a patch that silently didn't apply (name/namespace mismatch), a drift case where dev and prod overlays diverged from a shared base, a JSON6902 index breakage. Include real (sanitized) YAML fragments, the symptom, and the diagnosis path.

### 7. Test triggering and outputs
- Trigger evals: include near-misses that should NOT trigger — Helm questions, generic Kubernetes YAML questions, ArgoCD sync errors (that's skill #3's territory).
- Output evals: give it a broken overlay and check it finds the actual defect rather than listing generic possibilities.

### 8. Ship and iterate
Track the questions engineers ask that the skill answers vaguely — each vague answer marks a missing convention or reference file.

## Definition of done
- [ ] Encodes real repo layout and patch policy, not generic kustomize docs
- [ ] Asks for base/render output instead of guessing
- [ ] 2+ worked examples from real tickets
- [ ] Trigger evals pass including Helm/ArgoCD near-misses
- [ ] Owner assigned; linked to render pipeline PRD so version bumps update the skill
