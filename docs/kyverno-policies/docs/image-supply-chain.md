# Image Supply Chain Policies

Category: `image-supply-chain` · 3 policies · Waves 1 and 4 · PRD-2026-KYVERNO-POLICY-001

These policies ensure that what runs on the platform is traceable to what the CI pipelines built. They are the admission-side counterpart to the v2/v3 build pipeline controls (Cosign signing, Syft SBOM, Trivy scanning). System namespaces are excluded.

---

## disallow-latest-tag

**Severity: medium · Wave 1 · Test: `tests/image-supply-chain/disallow-latest-tag/`**

Blocks images using `:latest` or no tag at all. Mutable tags break GitOps reproducibility — the manifest in Git no longer determines what actually runs, and a rollback can silently deploy different bytes.

**How to comply:** Pin a version tag or (better) a digest:
```yaml
image: platformacr.azurecr.io/my-app:1.4.2
# or
image: platformacr.azurecr.io/my-app@sha256:abc123...
```
The render-to-Git CI pipeline (PRD-2026-CI-RENDER-001) already pins tags at render time, so violations here indicate workloads bypassing the pipeline.

---

## restrict-image-registries

**Severity: high · Wave 1 · Test: `tests/image-supply-chain/restrict-image-registries/`**

Restricts all containers and initContainers to the approved platform ACR hostnames. Images from arbitrary registries bypass every scanning, signing, and provenance control the platform provides.

**How to comply:** All images — including base images, sidecars, and third-party dependencies — must be imported into the platform ACR (or its pull-through cache) via the established import process, not pulled directly from Docker Hub/GHCR/etc.

**Placeholder warning:** The registry hostnames in the policy are placeholders and must be replaced with the real platform ACR names before merge.

---

## verify-image-signatures

**Severity: high · Wave 4 (STUB) · Test: `tests/image-supply-chain/verify-image-signatures/` (install-only)**

Verifies Cosign signatures on all images from the platform registry. This is the admission-side enforcement of the v3 ADO pipeline's signing step — an image that wasn't produced (and signed) by the platform build pipeline won't admit.

**Status:** Audit-only stub with a placeholder public key. Enforcement is **hard-blocked** on v3 pipeline Cosign signing reaching full fleet coverage (Wave 4). Enforcing earlier would block every unsigned-but-legitimate existing workload.

**Test note:** The Chainsaw test is install-only (asserts the policy becomes Ready). Full verification testing requires signed test images and the real platform key — add that fixture when Wave 4 approaches.
