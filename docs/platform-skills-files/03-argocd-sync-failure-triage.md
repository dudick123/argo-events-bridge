# Skill 3 — ArgoCD Sync Failure Triage

**Purpose:** Take a sync error, health status, or event stream and produce a categorized root cause with a fix path — turning tier-1 ArgoCD support into tenant self-service.

## Step-by-step

### 1. Scope the skill
- In scope: sync failures, OutOfSync/Degraded/Progressing-stuck diagnosis, hook failures, drift explanation, ignoreDifferences questions.
- Out of scope: manifest content bugs beyond what blocks sync (route to skill #1), pipeline failures upstream of Git (route to #4), Akuity platform outages (route to escalation).
- Primary users: tenants first, platform engineers second — write for the tenant's permission level.

### 2. Gather ground truth
- Your Application template conventions: sync options, retry policy, automated sync settings, `RespectIgnoreDifferences` usage, finalizers.
- The platform-managed `ignoreDifferences` entries and the reasoning for each — this is the single biggest source of "why is my app OutOfSync" confusion.
- Your AppProject boundaries and RBAC model — what tenants can and cannot see/do, so the skill gives instructions the asker can actually execute.
- Akuity-specific behaviors that differ from OSS ArgoCD (agent architecture, where events surface).
- A taxonomy of your last N sync-failure tickets, clustered into failure classes. This becomes the decision tree's branches.

### 3. Draft the skeleton
- SKILL.md: intake instructions (what to paste: app YAML, sync result, events) → failure-class decision tree → per-class diagnosis + fix → escalation criteria.
- Decision tree branches typically: manifest invalid at apply-time, RBAC/AppProject denial, hook/wave failure, CRD ordering, immutable field conflict, health-check misread, ignoreDifferences gap, controller/platform issue.
- `references/`: ignoreDifferences catalog with rationale, health-check customizations, Akuity-vs-OSS behavior notes.
- Description triggers: "sync failed", "OutOfSync", "app degraded", "stuck progressing", "ComparisonError", "hook failed", plus your ArgoCD app naming patterns.

### 4. Encode the intake contract
The skill's accuracy depends entirely on getting the right inputs. Specify exactly what to request and in what form (e.g., app spec, last sync operation result, recent events). Instruct the skill to ask for missing inputs *before* diagnosing rather than pattern-matching on a bare error string.

### 5. Declare blind spots
- No live cluster or Akuity API access — everything comes from what the engineer pastes.
- Must distinguish "this is your app's problem" from "this is a platform problem" honestly, and never tell tenants to attempt actions their RBAC forbids.

### 6. Add worked examples
One per major failure class, from real tickets: the pasted error, the diagnostic steps, the resolution. Include at least one case where the correct answer was "escalate to platform team" so the skill learns that ending is legitimate.

### 7. Test triggering and outputs
- Negatives: kustomize build errors (skill #1), pipeline failures (#4), generic Kubernetes pod crashloops.
- Output test: feed real historical errors, check the skill lands in the right branch of the tree and the fix matches what actually resolved it.

### 8. Ship and iterate
Measure deflection: track tickets where the tenant self-resolved using the skill vs. escalated anyway. Escalated tickets are your revision backlog.

## Definition of done
- [ ] Decision tree derived from real ticket taxonomy, not generic docs
- [ ] ignoreDifferences catalog with rationale included
- [ ] Intake contract makes the skill ask before guessing
- [ ] Tenant-RBAC-aware instructions (no unusable advice)
- [ ] Escalation criteria explicit; at least one worked example ends in escalation
