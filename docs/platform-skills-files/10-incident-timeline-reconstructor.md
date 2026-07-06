# Skill 10 — Incident Timeline Reconstructor

**Purpose:** Given exports of ArgoCD sync history, ADO deployment runs, and Datadog alerts for a time window, reconstruct a correlated "what changed and when" timeline for incident response and postmortems, and identify the most probable triggering change.

## Step-by-step

### 1. Scope the skill
- In scope: multi-source event correlation, timeline assembly, change-to-symptom hypothesis ranking, postmortem timeline drafting, ServiceNow change-record correlation.
- Out of scope: live incident *commands* (it analyzes evidence, it doesn't drive response), root-cause determination beyond "most probable triggering change" (correlation ≠ causation — the skill says so), monitoring configuration.
- Primary users: platform engineers during and after incidents.
- Build this one last: it consumes the data-access patterns and conventions the other skills establish.

### 2. Gather ground truth
- The export format for each source: what an Akuity/ArgoCD sync-history export looks like, an ADO run list export, a Datadog event/alert export, a ServiceNow CR export — actual field names, timestamp formats, and timezone behavior for each. Timestamp normalization is where naive correlation fails; document each source's quirks precisely.
- Your deployment topology knowledge: which ADO pipelines deploy to which clusters/namespaces, which ArgoCD apps map to which tenants — the join keys that let events from different systems be linked. (The change-bridge work already models much of this.)
- Known confounders: scheduled jobs, auto-sync ripples, node maintenance windows, alert flappiness patterns — things that appear in timelines but rarely cause incidents.
- 2–3 past incidents with their (manually built) timelines and actual root causes.

### 3. Draft the skeleton
- SKILL.md: evidence intake spec (which exports, which window — instruct requesting the window ± padding on both sides) → normalization rules (timestamps, timezone, join keys) → timeline assembly format → correlation heuristics → hypothesis-ranking rubric → output formats (live-incident brief vs. postmortem timeline).
- `references/`: per-source export field guides, join-key mapping, confounder catalog.
- Description triggers: "what changed", "incident timeline", "postmortem", "which deploy broke", "correlate alerts", "when did this start".

### 4. Encode the ranking rubric with epistemic honesty
Define how hypotheses are scored: temporal proximity, blast-radius match (did the change touch the failing component's dependency chain), change type risk, confounder discount. Require the output to present ranked *hypotheses with evidence*, never a single asserted cause — and to explicitly list changes that were ruled out and why, which is half a postmortem's value.

### 5. Declare blind spots
- Absence of evidence: the skill only sees the exports given. Require it to state the coverage window and sources examined, and to flag change classes it had no visibility into (manual kubectl actions, Azure portal changes, external dependencies) as unexcluded.
- Clock skew between systems — instruct it to treat sub-minute orderings as uncertain.

### 6. Define two output formats
- **Live-incident brief:** short — window, top 3 candidate changes with evidence, recommended verification action for each. Optimized for speed.
- **Postmortem timeline:** full normalized event table, narrative, ruled-out changes, visibility gaps. Optimized for completeness.
Fix both templates in SKILL.md.

### 7. Add worked examples
Reconstruct one past incident from raw exports through to the ranked hypothesis, showing the correct cause ranked first — and importantly, showing a plausible-but-innocent change being ruled out with reasoning.

### 8. Test triggering and outputs
- Negatives: monitoring setup questions (skill #8), single-app sync debugging (#3), capacity questions.
- Output test: feed a past incident's exports with the known answer withheld; check the true cause ranks in the top hypotheses and confounders are discounted.

### 9. Grow toward automation
Once export formats and heuristics stabilize, the manual-export intake can be replaced with scripted collection (the change-bridge polling infrastructure is the natural substrate). Design the skill's intake spec so the scripted version produces the same evidence bundle shape.

## Definition of done
- [ ] Per-source field guides with timestamp/timezone quirks documented
- [ ] Join-key mapping enables cross-system correlation
- [ ] Output is ranked hypotheses + ruled-out list, never a single asserted cause
- [ ] Coverage gaps and unexcluded change classes stated in every report
- [ ] Validated by blind reconstruction of a past incident
