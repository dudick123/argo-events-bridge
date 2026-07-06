# Platform Engineering Skill Build Guides

Step-by-step approaches for building 10 Claude agent skills for the platform team. Each guide is intentionally abstract — it tells you *what steps to take* and *what artifacts to gather*, not the platform-specific content itself (that comes from your repos, PRDs, and ticket history).

## The shared build lifecycle

Every skill in this set follows the same lifecycle. Individual guides reference these phases rather than repeating them.

1. **Scope** — Define what the skill answers, what it explicitly does not answer, and who asks. One skill per failure domain; resist merging.
2. **Gather ground truth** — Collect the real artifacts (configs, schemas, conventions, ticket transcripts) the skill will encode. This is the step that cannot be skipped or faked.
3. **Draft the skeleton** — SKILL.md with frontmatter (name + trigger-optimized description), a decision tree or workflow, and pointers to reference files. Keep SKILL.md under ~500 lines; push bulk material into `references/`.
4. **Encode conventions and blind spots** — State your platform's opinions with the *why* behind each. Explicitly declare what the skill cannot know (live cluster state, secrets, etc.) and what it should ask the engineer to provide.
5. **Add worked examples** — 2–3 real, anonymized incidents: symptom → diagnosis → fix. These teach the reasoning pattern.
6. **Test triggering** — Write ~20 realistic queries (half should-trigger, half tricky near-misses). Verify the skill loads when it should and stays quiet when it shouldn't. Make the description "pushy" if it undertriggers.
7. **Test outputs** — Run 3–5 realistic task prompts through Claude with the skill. Review answers for the two failure modes: vague genericism and confident wrong specifics.
8. **Ship, measure, iterate** — Release to the team, collect wrong/vague answers for two weeks, revise. Generalize from feedback — don't overfit to individual complaints.
9. **Maintain like code** — Skill lives in a repo, changes go through PR review, each skill has an owner, and updating the skill is part of the definition of done for any ADR/PRD change it encodes.

## Skill directory anatomy (applies to all)

```
skill-name/
├── SKILL.md            # workflow, decision tree, conventions, pointers
├── references/         # schemas, taxonomies, deep-dive docs (loaded on demand)
├── scripts/            # optional deterministic helpers
└── evals/              # test prompts + trigger queries
```

## The guides

| # | Skill | File |
|---|-------|------|
| 1 | Kustomize Overlay Analyzer | `01-kustomize-overlay-analyzer.md` |
| 2 | Kyverno Policy Impact Assessor | `02-kyverno-policy-impact-assessor.md` |
| 3 | ArgoCD Sync Failure Triage | `03-argocd-sync-failure-triage.md` |
| 4 | ADO Pipeline YAML Reviewer | `04-ado-pipeline-yaml-reviewer.md` |
| 5 | ESO / Key Vault Secret Wiring Debugger | `05-eso-keyvault-secret-debugger.md` |
| 6 | Envoy Gateway Migration Assistant | `06-envoy-gateway-migration-assistant.md` |
| 7 | AKS Upgrade Preflight Analyzer | `07-aks-upgrade-preflight-analyzer.md` |
| 8 | Datadog Query & Dashboard Builder | `08-datadog-query-dashboard-builder.md` |
| 9 | Tenant Onboarding Validator | `09-tenant-onboarding-validator.md` |
| 10 | Incident Timeline Reconstructor | `10-incident-timeline-reconstructor.md` |

## Suggested build order

Start with #5 (ESO debugger) or #3 (ArgoCD triage) — highest ticket volume, fastest feedback loop. Then #1/#2/#4, which can be partially extracted from the AI-assisted PR review plugin work. Leave #10 for last; it depends on data-source access patterns the others will establish.
