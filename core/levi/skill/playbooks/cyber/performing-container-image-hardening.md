---
skill_id: cyber_performing_container_image_hardening
name: Container Image Hardening
description: Harden container images through minimal bases, least privilege, and build-time security controls.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, hardening, devsecops]
version: 1.0.0
---

## Purpose

Most container images ship with more than they need: full OS userlands, package managers, shells, and known-vulnerable libraries — every one of them available to an attacker who compromises the workload. Image hardening shrinks that surface at build time so runtime defenses have less to protect. This playbook covers building minimal, least-privilege images: base image selection, dependency hygiene, non-root execution, and the CI gates that keep hardened images hardened.

## When to use

- Establishing secure image standards for a development organization.
- Reducing vulnerability scan noise from bloated base images.
- Preparing images for regulated or high-assurance environments.
- Remediating repeated "critical CVE in base image" findings at the source instead of per-image.
- Building golden/base images that product teams inherit from.

## Prerequisites

- A container build pipeline (CI) where standards can be enforced as gates.
- An approved base-image catalog: minimal bases (distroless, Alpine, or hardened minimal) matched to language runtimes.
- Image scanning integrated in CI (Trivy, Grype, or equivalent) with policy thresholds.
- Authority to set organization-wide build standards and block non-compliant images.
- A private registry with image signing support for provenance.

## Procedure

1. **Standardize on minimal base images.** Adopt distroless or minimal bases for each runtime; where a full distro is unavoidable, use the slim variant. Maintain the approved list centrally and review it quarterly — base images are the highest-leverage hardening decision.
2. **Minimize image contents.** Remove package managers, shells, and build tooling from final images via multi-stage builds: compile in a builder stage, copy only artifacts into the runtime stage. Every binary in the final image should be justifiable; document exceptions.
3. **Pin and update dependencies deliberately.** Pin base image digests (not floating tags) for reproducible builds, and automate rebuilds on base-image or dependency updates. Pair pinning with a freshness SLA — pinned-and-forgotten images accumulate CVEs silently.
4. **Run as non-root.** Set a dedicated non-root `USER`, make the filesystem read-only where the application allows, and drop Linux capabilities to the minimum (often none beyond the defaults your runtime requires). Verify at runtime that the process is not root — Dockerfiles lie when entrypoints escalate.
5. **Harden the build itself.** Build from trusted contexts, verify base image signatures, avoid `curl | sh` in Dockerfiles, and keep secrets out of layers (use build secrets, never `ENV` or committed files). Scan the Dockerfile with a linter (Hadolint, Dockle) as a CI gate.
6. **Sign and attest.** Sign images (Cosign/Sigstore) and attach SBOMs and provenance attestations at build time. Configure admission control to require valid signatures before deployment — hardening means little if anyone can deploy an unsigned replacement.
7. **Gate in CI.** Enforce: vulnerability threshold (fail on critical/high without waiver), Dockerfile lint, non-root verification, and signature presence. Waivers must be time-boxed and tracked, not permanent exceptions.
8. **Maintain continuously.** Rebuild images on a schedule regardless of application changes (to absorb base-image patches), monitor the approved base list for deprecations, and review waiver backlogs monthly.

## Expected outputs

- An approved base-image catalog with minimal, pinned, signed images per runtime.
- Hardened Dockerfile standards: multi-stage, non-root, minimal contents, linted.
- CI gates: vulnerability thresholds, lint, signature, and provenance checks.
- Signed images with SBOMs in the registry; admission policy enforcing signatures.
- A rebuild and waiver-maintenance cadence with owners.

## Pitfalls

- Pinning digests but never rebuilding — reproducibility without freshness is just frozen vulnerability.
- Assuming `USER nobody` in the Dockerfile guarantees non-root at runtime; entrypoint scripts and orchestrator `securityContext` can override it. Verify running state.
- Secrets baked into layers via `ENV` or `COPY` — they persist in layer history even if deleted in a later layer.
- Waivers that never expire, quietly exempting the riskiest images from the gates meant to catch them.
- Hardening the image but deploying it privileged with host mounts — image hardening and runtime hardening must be done together.

## References

- NIST SP 800-190, "Application Container Security Guide"
- CIS Docker Benchmark (image configuration controls)
- Sigstore/Cosign documentation for image signing
- Docker official documentation on multi-stage builds and build secrets
- OWASP guidance on container security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
