# Skill 6 — Envoy Gateway Migration Assistant

**Purpose:** Help engineers translate legacy ingress configurations into Gateway API resources per platform contracts, validate HTTPRoute/ClientTrafficPolicy configs, and answer "how do we do X on Envoy Gateway here" without relitigating settled architecture decisions.

## Step-by-step

### 1. Scope the skill
- In scope: legacy-to-Gateway-API translation, HTTPRoute/policy authoring guidance, feature-mapping questions ("Kong did X, what's the equivalent"), migration sequencing for a given tenant, config validation.
- Out of scope: the architecture decision itself (settled — the skill cites the ADRs, it doesn't reopen them), DNS/NSG change execution (process pointers), post-migration performance debugging (candidate future skill fed by the k6 work).
- Primary users: platform engineers executing migrations; tenants preparing their configs.

### 2. Gather ground truth
- The migration PRD and both ADRs — extract the decisions and their rationale into skill-consumable form.
- Your Gateway API contract: which resources tenants own vs. platform owns, the custom operator's CRD contract and what it generates, naming conventions, shared-vs-dedicated Gateway policy.
- The security controls layer: ClientTrafficPolicy patterns for mTLS (Imperva), NSG allowlisting model, TLS termination points — and the explicit "why no Azure Firewall inbound" argument, because that question will recur.
- A feature-mapping table: every legacy capability in use (auth plugins, rate limiting, rewrites, header manipulation) → its Envoy Gateway equivalent or its "not supported, here's the alternative" answer. Build this from an inventory of what tenants actually use, not the full legacy feature list.
- One completed migration as the canonical worked example.

### 3. Draft the skeleton
- SKILL.md: decision context (what was decided, where the ADRs live) → ownership model (who writes what) → translation workflow (inventory legacy config → map features → generate Gateway API resources → validate → cutover checklist) → validation rules.
- `references/`: feature-mapping table, ClientTrafficPolicy/security patterns, operator CRD contract, cutover checklist.
- Description triggers: "envoy gateway", "HTTPRoute", "Gateway API", "migrate from kong", "ingress migration", "ClientTrafficPolicy", "mTLS ingress", legacy ingress class names.

### 4. Encode the settled decisions defensively
Mid-migration, engineers will propose things the ADRs already rejected. Give the skill the rejected alternatives and the reasons, and instruct it to answer "we considered that; here's why we didn't" with the ADR reference — respectful, but firm, with an escalation path if someone believes circumstances have changed.

### 5. Declare blind spots
- The feature-mapping table is a snapshot; Envoy Gateway moves fast. Instruct the skill to state the table's as-of version and flag when a question concerns capabilities that may have changed since.
- It cannot verify what a tenant's legacy config actually does in production — always ask for the actual config export, never work from a tenant's description of it.

### 6. Add worked examples
The canonical completed migration end-to-end: legacy config in → mapped features → generated resources → cutover steps. Plus one "unsupported feature" case showing how the alternative was negotiated.

### 7. Test triggering and outputs
- Negatives: general Kubernetes Service/networking questions, Cilium policy questions, cert questions unrelated to ingress.
- Output test: feed a legacy config with one unsupported feature planted; verify the skill catches it and proposes the documented alternative rather than hallucinating support.

### 8. Plan for sunset
This skill has a natural end-of-life when migration completes. Note in the skill's repo metadata what survives it (the Gateway API authoring guidance) versus what retires (translation workflow) — plan to split rather than let it rot whole.

## Definition of done
- [ ] ADR decisions and rejected alternatives encoded with rationale
- [ ] Feature-mapping table built from actual tenant usage inventory
- [ ] One full worked migration included
- [ ] Skill requests real config exports, never works from descriptions
- [ ] Sunset/split plan noted for post-migration
