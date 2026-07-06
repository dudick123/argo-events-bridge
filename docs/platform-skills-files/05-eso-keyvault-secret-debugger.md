# Skill 5 — ESO / Key Vault Secret Wiring Debugger

**Purpose:** Systematically diagnose "my secret isn't showing up" by walking the full delivery chain — Key Vault → workload identity → SecretStore → ExternalSecret → Kubernetes Secret → pod consumption.

## Step-by-step

### 1. Scope the skill
- In scope: end-to-end secret delivery failures, refresh/rotation issues, templating problems, identity federation misconfiguration diagnosis.
- Out of scope: granting Key Vault access (process pointer only), secret content questions (never handle secret values), non-ESO secret mechanisms (there are none on this platform — say so and redirect attempts).
- Primary users: tenants; the skill must work within tenant visibility limits.

### 2. Gather ground truth
- The full chain as built on your platform: how ClusterSecretStore/SecretStore scoping works (namespace selectors, tenant labels), the workload identity federation pattern (including the Kyverno annotation-injection mutation), Key Vault naming/structure conventions, RBAC assignment model.
- Standard ExternalSecret patterns tenants use: refresh intervals, `target.template` usage, creation policy.
- The observable signals at each chain link: what status conditions, events, and error messages appear where, and what each actually means on your setup (ESO error messages are notoriously indirect).
- Ticket history: your most common failure modes ranked by frequency. This ordering shapes the diagnostic sequence — check common causes first.

### 3. Draft the skeleton
- SKILL.md: the chain diagram (conceptual, as text) → intake contract (what to paste: ExternalSecret YAML + status, SecretStore status, pod events) → link-by-link diagnostic walk, ordered by failure frequency → per-failure fix guidance → escalation criteria.
- `references/`: naming convention spec, error-message-to-cause mapping table, identity federation deep-dive (including the blue-green upgrade wrinkle).
- Description triggers: "secret not found", "ExternalSecret", "SecretStore", "key vault", "secret not syncing", "SecretSyncedError", "workload identity", "403 keyvault".

### 4. Encode the diagnostic walk as an ordered procedure
The chain structure is the skill's core asset. For each link: what to check, what command/output to request, what healthy looks like, what each unhealthy state means, and which link to jump to next. Explicitly instruct: complete the current link before advancing — chain-skipping is how humans misdiagnose these, and the skill should model the discipline.

### 5. Declare blind spots — this skill has the most
- Never ask for or accept secret *values*; work only from metadata, status, and error text. State this prominently.
- Never guess Key Vault names, secret names, or client IDs — the naming convention constrains the pattern, but the skill must ask for the actual values (names only) rather than constructing them.
- Cannot see Azure-side state (RBAC assignments, federation credentials) — instruct it to give the engineer the exact Azure-side checks to run and interpret pasted results.

### 6. Add worked examples
Use your real greatest hits: a scoping failure (SecretStore selector not matching tenant namespace), an identity failure (federation subject mismatch after cluster swap), a templating failure. Verbatim (sanitized) symptoms, the walk, the fix.

### 7. Test triggering and outputs
- Negatives: Kubernetes Secret RBAC questions unrelated to ESO, cert-manager questions, "how do I add a secret to Key Vault" process questions (should route to process docs, not debugging).
- Output test: give partial information and verify the skill asks for the next link's evidence instead of concluding prematurely.

### 8. Ship first, measure hardest
This is likely your highest-volume skill — ship it before the others and use its two-week feedback window to calibrate your approach for the rest.

## Definition of done
- [ ] Chain walk ordered by real failure frequency
- [ ] Error-message-to-cause mapping built from actual observed errors
- [ ] Hard rule against handling secret values, stated in-skill
- [ ] Skill requests evidence link-by-link rather than concluding early
- [ ] Azure-side checks phrased as instructions the tenant can relay/run
