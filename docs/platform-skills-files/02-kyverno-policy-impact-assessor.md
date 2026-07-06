# Skill 2 — Kyverno Policy Impact Assessor

**Purpose:** Assess which workloads a policy would affect before enforcement, interpret audit results, recommend exemption vs. remediation per tenant, and draft tenant-facing communications.

## Step-by-step

### 1. Scope the skill
- In scope: policy readability review, audit report interpretation, blast-radius reasoning, exemption criteria, rollout phasing advice, tenant communication drafting.
- Out of scope: authoring net-new policies from scratch (separate concern), Cilium network policy (that's the zero-trust workstream — cross-reference, don't duplicate).
- Primary users: platform engineers running the enforcement rollout.

### 2. Gather ground truth
- Your policy framework's structure from the Kyverno policy PRD: policy naming scheme, severity/category labels, rollout phase definitions, and the audit → warn → enforce progression rules.
- Your exemption mechanism: how exceptions are granted (PolicyException, namespace labels, annotations), who approves, how long they live.
- The workload-profile annotation scheme (your four active profiles) — policies frequently key off these.
- Example PolicyReport/ClusterPolicyReport output from your clusters (sanitized).
- 2–3 real enforcement decisions: a policy that went to enforce cleanly, one that needed tenant remediation first, one that got a permanent exemption — with the reasoning.

### 3. Draft the skeleton
- SKILL.md sections: policy framework overview → impact assessment workflow (parse audit results → group by tenant → classify each violation as remediate/exempt/policy-bug) → rollout phasing guide → communication templates.
- `references/`: full policy catalog with intent statements, exemption policy doc, PolicyReport field guide.
- Description triggers: "kyverno", "policy would block", "audit results", "enforce this policy", "policy exception", "which tenants fail".

### 4. Encode the decision framework, not just facts
The core value is the *classification logic*: given a violation, is it (a) tenant misconfiguration → remediation with deadline, (b) legitimate exception → documented exemption, or (c) policy bug/over-breadth → fix the policy. Write the criteria for each branch and the escalation path when ambiguous.

### 5. Declare blind spots
- The skill cannot query clusters. Instruct it to ask for PolicyReport exports or `kubectl` output in a specified format, and to state assumptions when working from partial data.
- It must not assert current enforcement state of any policy — that changes; ask.

### 6. Add worked examples
Include one full assessment: raw audit output in → per-tenant classification table + draft comms out. This anchors the expected output format.

### 7. Define output formats explicitly
Impact assessments and tenant comms benefit from fixed templates (summary → affected tenants → required action → deadline → exemption path). Put the template in SKILL.md so outputs are consistent across engineers.

### 8. Test triggering and outputs
- Near-miss negatives: Cilium/NetworkPolicy questions, generic admission webhook questions, Gatekeeper/OPA questions.
- Output test: feed a sanitized audit report, verify classification matches what the team actually decided historically.

## Definition of done
- [ ] Classification criteria (remediate/exempt/fix-policy) encoded with reasoning
- [ ] Exemption process and approval path documented
- [ ] Communication template produces consistent tenant-facing output
- [ ] Worked end-to-end assessment example included
- [ ] Linked to the Kyverno policy PRD; policy catalog reference regenerated when policies change
