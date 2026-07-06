# Skill 4 — ADO Pipeline YAML Reviewer

**Purpose:** Review Azure DevOps pipeline YAML against platform template conventions — parameter contracts, stage/job structure, secret handling, timeouts, and artifact handoff patterns — so every pipeline PR gets senior-level review.

## Step-by-step

### 1. Scope the skill
- In scope: pipeline YAML structure review, template usage correctness, convention enforcement, anti-pattern detection, "how do I do X in our templates" guidance.
- Out of scope: debugging live pipeline run failures (different inputs — logs, not YAML; decide whether that's a v2 or a sibling skill), the internals of the templates themselves (engineers consume, platform maintains).
- Primary users: tenant engineers and junior platform engineers writing/modifying pipelines.

### 2. Gather ground truth
- The current template catalog: each template's parameter contract (name, type, required/optional, defaults), what it produces, and which version (v2/v3) is current vs. deprecated.
- Cross-cutting conventions: dependency chaining patterns, timeout policy (per-resource timeout blocks), parallelism rules, service connection usage, variable group vs. Key Vault–backed secret policy.
- The artifact handoff contracts between pipelines (e.g., how the build pipeline's signed image reference flows into deploy).
- Anti-patterns you've corrected in past reviews — mine your PR comment history; each recurring comment is a rule for the skill.

### 3. Draft the skeleton
- SKILL.md: review workflow (structure → template usage → parameters → secrets → timeouts → handoffs) → convention rulebook with rationale → common-mistakes catalog → review output format.
- `references/`: per-template parameter contract docs (one file per template family), deprecation/migration notes (v2→v3).
- Description triggers: "azure-pipelines", "pipeline yaml", "ADO pipeline", "review my pipeline", "template parameters", stage/job/step vocabulary, your template repo name.

### 4. Encode conventions as review rules with severity
Give each rule a severity (blocker / should-fix / suggestion) and a why. Example shape: "Blocker: secrets via inline variables — all secrets flow through Key Vault–backed groups because inline values leak into run logs and forks." Severity keeps review output actionable rather than a wall of nitpicks.

### 5. Define the review output format
Fix a template: summary verdict → blockers → should-fix → suggestions, each with file/line reference and suggested change. Consistent format makes the skill's output pasteable directly into a PR review.

### 6. Declare blind spots
- The skill cannot resolve template repos it hasn't been given — instruct it to ask for the referenced template's contract (or point to the reference file) rather than inferring parameters.
- It must not assert which template version is "latest" — versions change; the reference file is authoritative, and the skill should flag when a reviewed pipeline references a template absent from the references.

### 7. Add worked examples
Two or three real PR diffs (sanitized): the submitted YAML, the review comments the team actually made, the corrected version. This calibrates tone and severity.

### 8. Test triggering and outputs
- Negatives: GitHub Actions YAML, Kubernetes manifests, questions about ADO boards/repos administration.
- Output test: feed a pipeline with 3 planted violations of different severities; verify all are caught, correctly ranked, and no phantom issues are invented.

### 9. Maintain
Template changes are the drift risk. Add "update reviewer skill reference file" to the template repo's PR checklist — the skill's reference docs should be generated from or reviewed against the templates in the same change.

## Definition of done
- [ ] Every template family has a parameter-contract reference file
- [ ] Rules carry severity + rationale, mined from real review comments
- [ ] Fixed review output format, pasteable into PRs
- [ ] Skill flags unknown templates instead of guessing contracts
- [ ] Template repo PR checklist includes skill reference updates
