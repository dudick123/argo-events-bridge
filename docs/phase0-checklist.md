# Phase 0 Prerequisites Checklist

These items must be completed before any bridge code is deployed to WUS3. Each item has a clear owner type (Platform, Security, Dev) and a done condition.

---

## Infrastructure

### [ ] 1. Deploy In-Cluster HA Redis (WUS3)

**Owner:** Platform
**Done when:** Redis Sentinel is running in `snow-bridge-gitops` namespace on WUS3, accessible at a stable service DNS name, and survives a pod kill without data loss.

Steps:
- Add Bitnami Redis Helm chart to the platform GitOps repo
- Configure Sentinel mode with 3 replicas
- Set appropriate resource requests/limits and PodDisruptionBudget
- Verify failover behavior

**Open question:** What PVC storage class should Redis use on WUS3? Confirm with platform team.

---

### [ ] 2. Create Namespace `snow-bridge-gitops` (WUS3)

**Owner:** Platform
**Done when:** Namespace exists on WUS3 with appropriate labels and NetworkPolicy applied per platform standards.

---

## Secrets & Access

### [ ] 3. Akuity API Key → Azure Key Vault

**Owner:** Security / Platform
**Done when:** The existing Akuity API key is stored as a secret in the org's Azure Key Vault instance, accessible by the ESO SecretStore on WUS3.

Note: The API key already exists. This task is only adding the Key Vault entry and ESO wiring.

**Open question:** Which Key Vault instance hosts platform secrets on WUS3? Confirm vault name and resource group.

---

### [ ] 4. SNOW API Credentials → Azure Key Vault

**Owner:** Security
**Done when:** SNOW test instance credentials are stored in Key Vault and the secret type (API key vs client credentials) is confirmed.

Dependency: SNOW API contract (see `docs/snow-api-contract.md`) must be confirmed before the right credential format is known.

**Open question:** Does the SNOW test instance use the same credential type as production? Are separate creds needed per environment?

---

### [ ] 5. Configure ESO SecretStore and ExternalSecrets (WUS3)

**Owner:** Platform
**Done when:** ESO `SecretStore` or `ClusterSecretStore` on WUS3 is pointed at the correct Key Vault; `ExternalSecret` objects for Akuity key and SNOW credentials are created in `snow-bridge-gitops` namespace and syncing successfully.

---

## API Validation

### [ ] 6. Validate Akuity List API Response Shape

**Owner:** Dev
**Done when:** A manual `curl` or script against the Akuity API confirms:

- [ ] The list endpoint returns full `operationState` per app (not summaries)
- [ ] The response envelope shape (`items` array vs. other) is known
- [ ] `initiatedBy.username` format is confirmed for both UI-triggered and API-triggered syncs
- [ ] `operationState` is `null` (not absent/empty) when no operation is running
- [ ] `status.history` is ordered most-recent-first
- [ ] The `?selector=env=prod` label filter works as expected and returns only prod apps
- [ ] Response size for ~500 apps is within acceptable HTTP timeout bounds

**Deliverable:** Update `docs/akuity-api-examples.md` with confirmed response shapes and close open questions 1–8.

---

### [ ] 7. Confirm Akuity API Rate Limits

**Owner:** Dev
**Done when:** Rate limit thresholds are confirmed (via Akuity support, documentation, or empirical testing) and the `AKUITY_MIN_REQUEST_INTERVAL_MS` default is set appropriately.

---

### [ ] 8. Confirm SNOW CR API Contract

**Owner:** Dev + SNOW team
**Done when:** All open questions in `docs/snow-api-contract.md` are answered and the document is updated with confirmed endpoint paths, payload field names, and authentication mechanism.

This is a **blocking dependency** for Phase 1 development of the SNOW client.

---

### [ ] 9. Confirm SNOW Test Instance Access

**Owner:** Dev
**Done when:** The bridge can successfully call the SNOW test instance create endpoint and receive a `sys_id` in response. End-to-end test: create → close → attach.

---

## Completion Gate

Phase 1 development should not begin until items 1, 2, 3, 4, 5, 6, and 8 are complete. Items 7 and 9 can be validated in parallel with early Phase 1 development.

---

## Open Questions

1. **Key Vault identity** — Which Key Vault instance and resource group hosts platform secrets on WUS3? Who owns access policy management?

2. **ESO version** — What version of ESO is deployed on WUS3? Confirm `SecretStore` vs `ClusterSecretStore` pattern used by other workloads.

3. **Redis storage class** — What PVC storage class should be used for Redis persistence on WUS3?

4. **Namespace provisioning process** — Is `snow-bridge-gitops` created via a GitOps PR to the platform repo, or via a manual request? Who approves?

5. **SNOW test instance** — Is there an existing SNOW test/dev instance the team can use for Phase 1 validation, or does one need to be requested?
