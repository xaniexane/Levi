---
skill_id: cyber_implementing_sigstore_for_software_signing
name: Implementing Sigstore for Software Signing
description: Adopt Sigstore keyless signing and transparency logging to secure software build artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, code-signing, sigstore]
version: 1.0.0
---
## Purpose
This playbook describes how to introduce Sigstore — keyless signing with Fulcio, artifact transparency via Rekor, and verification policy — into a build and release pipeline, so consumers can verify that an artifact came from the claimed CI system and has not been tampered with.

## When to use
- Publishing container images, language packages, or release binaries that others depend on.
- Responding to supply-chain requirements from customers or regulators (e.g., SLSA provenance expectations).
- Replacing long-lived signing keys that are painful to rotate and store.

## Prerequisites
- A CI/CD system with OIDC identity support (GitHub Actions, GitLab CI, or equivalent).
- Inventory of artifacts to sign: container images, tarballs, SBOMs, attestations.
- A verification policy decision: who verifies, where (admission controllers, package managers, internal tooling).

## Procedure
1. **Select the trust root.** Decide between the public Sigstore instance and a private deployment (Fulcio + Rekor + TSA) for air-gapped or regulated environments.
2. **Instrument the build.** Add a signing step after artifact creation using `cosign sign` for containers or `gitsign` for commits, bound to the CI workload's OIDC identity (e.g., the repository and workflow that produced it).
3. **Emit SLSA provenance.** Generate in-toto/SLSA attestations describing source, builder, and materials, and sign the attestation alongside the artifact.
4. **Publish to Rekor.** Ensure every signature is recorded in the transparency log so signatures are publicly auditable and cannot be issued silently.
5. **Enforce verification on consume.** Configure admission control (e.g., a Kubernetes policy engine) or deployment gates to reject artifacts whose signatures or expected OIDC identities do not verify.
6. **Document keyless rotation.** Because identities come from OIDC, rotation means rotating the CI identity configuration, not distributing new keys; write this into the key-management runbook.
7. **Monitor the transparency log.** Watch for certificates or entries issued for your identities that you did not expect — a signal of CI compromise.

8. **Handle key compromise and revocation.** Document the incident path: rotate CI identities, publish revocations, and notify consumers to re-verify artifacts built during the compromise window.
9. **Extend to SBOMs and attestations.** Sign SBOMs and vulnerability scan attestations alongside binaries so consumers get integrity plus transparency in one verification step.

## Expected outputs
- Signed release artifacts with Rekor transparency entries and SLSA provenance.
- Verification policy enforced at deployment/consumption points.
- Runbook for identity rotation and incident response for suspected signing abuse.
- Example: a container image signed by the release workflow's OIDC identity, with `cosign verify` succeeding in the admission controller and the Rekor entry UUID recorded in the release notes.

## Pitfalls
- Signing without verification enforcement gives a false sense of security; the value is in the check, not the signature.
- Assuming public Sigstore is acceptable for all artifacts; regulated data may require a private instance.
- OIDC identity sprawl: overly broad CI identities let any workflow sign as the release pipeline.

- Signing in CI but storing artifacts in a mutable registry where tags can be repointed after signing; sign digests, and verify digests, not tags.
- Forgetting that transparency logs are public: never put sensitive internal hostnames or usernames in attestation fields that end up in Rekor.

## References
- Sigstore documentation (docs.sigstore.dev).
- SLSA framework (slsa.dev) — provenance and build integrity levels.
- NIST SP 800-204D, Strategies for the Integration of Software Supply Chain Security.
- NIST SP 800-161 Rev. 1, Cybersecurity Supply Chain Risk Management Practices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
