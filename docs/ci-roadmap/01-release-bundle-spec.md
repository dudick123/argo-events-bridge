# 01 — Release Bundle Specification

**Parent:** ARCH-2026-CI-ARTIFACT-001 §3, Principles P1 (immutability) and P2 (bundle as release unit)
**Feature prefix:** `RB`
**Contract freeze required before:** Docs 03, 05, 06, 07 begin implementation

---

## Executive Summary

The Release Bundle is the atomic unit of delivery for the entire platform: a single OCI artifact graph, rooted at one digest, that binds a container image, its fully rendered Kubernetes configuration, and its complete attestation set (provenance, SBOM, scans, policy reports). Every downstream system — registry policy, promotion, reconciliation, admission, observability — keys off this one contract. Getting the specification right, versioned, and frozen early is the single highest-leverage activity in the program: a weak spec here becomes a migration project everywhere else. This document defines the bundle's structure, media types, versioning rules, and lifecycle, and lays out the work to deliver a v1 specification, reference tooling (`bundle-cli`), and conformance tests within Phase 0–1.

**Why it matters to the business:** the bundle collapses "what version of the app, what config, and what security posture is running in prod?" into one digest lookup — reducing audit effort, incident triage time, and the class of outages caused by image/config skew to near zero.

---

## Principle Breakdown

### P1 — Immutability end to end
- Content-addressing is the enforcement mechanism, not a convention. Machines reference digests exclusively; tags exist only as human-facing aliases (`v1.4.2`, `prod-current`) and are never resolution inputs for any automated consumer.
- Immutability applies to the *graph*: attaching a new attestation (e.g., a fresh vuln scan) uses the OCI referrers mechanism and does not alter the subject digest. Post-publication enrichment is additive-only.
- Corollary: nothing downstream ever re-renders, patches, or templates. If an environment needs a different value, that is a *different bundle*, produced upstream.

### P2 — The bundle, not the image, is the release
- Image/config skew is the dominant cause of "works in staging, fails in prod." The bundle makes skew unrepresentable: promotion moves the root digest, and image + config travel together by construction.
- The bundle is also the unit of *trust*: verification policy evaluates the graph (is the image signed? does provenance match the config's source commit? is the scan attestation fresh?), not isolated artifacts.

## Specification (v1 outline)

```
oci://<registry>/<org>/<app>/bundle@sha256:<root>
  manifest (OCI image index or artifact manifest)
    annotations:
      org.example.bundle.schema-version: "1"
      org.example.bundle.app: <app>
      org.example.bundle.source-commit: <sha>
      org.example.bundle.environment-class: <dev|nonprod|prod>
      org.example.bundle.render-toolchain: <toolchain-digest>
  layers / referenced artifacts:
    - image (by digest reference, standard OCI image)
    - config layer: application/vnd.org.k8s-manifests.v1.tar+gzip
        (plain, fully hydrated YAML; deterministic file ordering; no secrets)
  referrers (attached via OCI referrers API, each a signed in-toto envelope):
    - SLSA provenance (predicate: https://slsa.dev/provenance/v1)
    - SBOM (SPDX or CycloneDX predicate)
    - vulnerability scan report (timestamped)
    - policy evaluation report (schema + admission-policy pre-check results)
    - signature (Sigstore bundle format)
```

**Key spec decisions to ratify (ADRs):**
1. Index-of-references vs. fat artifact — recommend index-of-references: image stays a normal pullable image; config is a small separate artifact; bundle root is a lightweight index. Enables independent caching and standard runtime pulls.
2. One bundle per environment-class (recommended) vs. one bundle with all env configs — per-env keeps pulls minimal and blast radius scoped; version them under a shared release annotation.
3. Media type namespace and schema-version evolution policy (additive fields only within a major).
4. Secrets stance: reference-only (ExternalSecret/SecretProviderClass style manifests allowed; raw `Secret` kinds rejected at publish).
5. Determinism rules for the config layer: stable file naming, sorted keys, normalized whitespace — required for byte-identical rebuilds and meaningful digest comparison.

## Implementation Roadmap

| Phase | Timeframe | Milestones |
|---|---|---|
| 0 | M0–M2 | Spec v1 drafted; ADRs 1–5 ratified; media types registered internally |
| 0 | M2–M3 | `bundle-cli` v0: assemble, push, pull, inspect, verify-structure |
| 1 | M3–M6 | Conformance test suite; schema-validation of annotations; determinism verifier; referrers round-trip tests against target registry |
| 1 | M6–M9 | `bundle-cli` v1 GA: attestation attach/list/verify subcommands; library (SDK) extraction for pipeline + promotion consumers |
| 2+ | M9+ | Spec v1.x additive extensions as consumers surface needs (e.g., multi-arch config variants, delta layers) |

## Jira Features

| ID | Feature | Description | Outcome / Done criteria | Depends on |
|---|---|---|---|---|
| FEAT-RB-01 | Release Bundle Specification v1 | Author the normative spec: structure, media types, annotations, lifecycle, determinism rules. Ratify ADRs 1–5. | Spec merged to platform repo; ADRs approved; downstream teams sign off on contract freeze | — |
| FEAT-RB-02 | Bundle assembly & publish tooling (`bundle-cli` v0) | CLI (ORAS-based) that assembles a bundle from an image ref + rendered config dir, pushes to registry, sets annotations. | CI can produce a spec-conformant bundle in a sandbox registry; inspect/pull round-trips | RB-01 |
| FEAT-RB-03 | Deterministic config layer builder | Canonicalization library: stable ordering, normalized YAML, reproducible tar+gzip (fixed timestamps/permissions). | Two builds of identical inputs yield identical layer digests; verifier in CI | RB-01 |
| FEAT-RB-04 | Attestation attachment & discovery | Attach/list signed in-toto envelopes via referrers API; graceful fallback strategy if target registry lacks referrers support. | Provenance/SBOM/scan/policy attestations discoverable from root digest with one API pattern | RB-01, SCT-01 |
| FEAT-RB-05 | Bundle conformance test suite | Automated suite validating structure, annotations, determinism, and referrers behavior; run against candidate registries. | Suite gates registry selection (Doc 05) and pipeline template releases (Doc 03) | RB-02, RB-03 |
| FEAT-RB-06 | Bundle SDK | Extract cli internals into a library consumed by pipeline templates, promotion steps, and the ledger service. | Promotion controller and ledger integrate without shelling out to the CLI | RB-02–04 |
| FEAT-RB-07 | Bundle lifecycle & deprecation policy | Define/pin/retention semantics: promoted-digest pinning, unpromoted TTL, schema-version deprecation process. | Policy doc + machine-readable retention rules handed to Doc 05 | RB-01 |

## Risks
- **Registry referrers support variance** — mitigated by RB-04 fallback design and RB-05 gating registry choice.
- **Spec churn after freeze** — mitigated by additive-only evolution rule and an explicit v2 escape hatch with dual-publish window.

## References
- OCI Image Spec — artifact usage guidance: https://github.com/opencontainers/image-spec/blob/main/manifest.md
- OCI Distribution Spec v1.1 — referrers API: https://github.com/opencontainers/distribution-spec/blob/main/spec.md
- ORAS — pushing arbitrary artifacts: https://oras.land/docs/
- in-toto Attestation Framework (ITE-6 envelope): https://github.com/in-toto/attestation
- Sigstore bundle format: https://docs.sigstore.dev/about/bundle/
- Argo CD OCI source media-type expectations: https://argo-cd.readthedocs.io/en/latest/user-guide/oci/
- Carvel imgpkg (prior art for manifest bundles + relocation): https://carvel.dev/imgpkg/
- Reproducible Builds project (determinism practices): https://reproducible-builds.org/docs/
