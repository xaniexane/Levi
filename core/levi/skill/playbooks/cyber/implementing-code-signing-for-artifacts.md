---
skill_id: cyber_implementing_code_signing_for_artifacts
name: Code Signing for Build Artifacts
description: Implement code and artifact signing so every deployed binary is authenticated and tamper-evident.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, signing]
version: 1.0.0
---
## Purpose
Unsigned artifacts can't prove their origin: a compromised build server, mirror, or registry can
ship trojaned binaries that look legitimate. Code signing binds artifacts to their producer with
cryptographic signatures, and verification at deploy time ensures only authentic, unmodified
artifacts run. This playbook implements signing for build artifacts end-to-end: key management,
pipeline integration, and deployment-time verification.

## When to use
- Securing the software supply chain against build-time and distribution-time tampering.
- Meeting supply-chain requirements (SLSA, EO 14028, customer security questionnaires).
- After incidents involving compromised updates or trojaned dependencies.
- Before shipping software to customers or deploying to production from CI/CD.
- As the authenticity layer beneath image scanning and admission control.

## Prerequisites
- A signing key strategy: HSM or cloud KMS-backed keys (never keys on build workers), with separate
  keys per product/environment tier.
- A signing authority decision: internal PKI, Sigstore (keyless), or commercial CA — matched to
  artifact consumers' trust needs.
- CI/CD access to insert signing steps and artifact stores that preserve signatures.
- Deployment-time verification points: admission controllers, package managers, installers, or
  update clients that check signatures.
- A key-compromise and rotation plan written before the first signature.

## Procedure
1. **Choose the signing model.** For open-source/customer-facing artifacts: Sigstore (keyless,
   transparency-log-backed) or CA-issued certificates. For internal artifacts: private PKI or
   KMS-backed keys. Document what each signature asserts (built by which pipeline, from which source
   commit).
2. **Protect signing keys properly.** Generate keys in an HSM or cloud KMS; grant signing permission
   only to the CI/CD pipeline identity (OIDC-federated, short-lived — not long-lived credentials on
   workers). No human should ever handle the private key. Enable key-usage logging and alerting.
3. **Sign at build time, automatically.** Insert signing into the pipeline immediately after
   artifact creation: container images (cosign), language packages, binaries, installers, and SBOMs.
   Sign the SBOM too — it attests to what's inside. Fail the build if signing fails; unsigned
   artifacts must never be publishable.
4. **Record signatures transparently.** Publish to a transparency log (Sigstore Rekor) or internal
   append-only record: artifact hash, signer identity, timestamp. Transparency makes clandestine
   signing detectable and gives auditors the provenance trail.
5. **Verify at every consumption point.** Enforce verification: Kubernetes admission controller
   (signed images only), package manager signature checks, OS-level driver/app signing enforcement,
   and update-client verification. Signing without verification is a ritual — the enforcement points
   are the control.
6. **Bind signatures to source.** Include provenance: source repo, commit SHA, build pipeline ID,
   and build parameters in the signed attestation (SLSA provenance). Verification then answers not
   just "who signed" but "built from what, by which pipeline."
7. **Manage the key lifecycle.** Rotate signing keys on schedule (annually or per policy) and
   immediately on suspected compromise. Maintain a revocation/distrust mechanism consumers honor;
   keep old public keys for verifying historical artifacts during the transition window.
8. **Handle developer and emergency flows.** Define: how developers sign local test builds (dev-only
   keys, clearly marked, never deployable to prod), and the emergency process if signing
   infrastructure is down (pre-approved break-glass with dual control and post-incident review — not
   a permanent bypass).
9. **Monitor signing operations.** Alert on: signing failures (build integrity issue), signatures
   from unexpected pipeline identities, key-usage anomalies, and verification failures at deploy
   time (possible tampering or stale trust config). These are supply-chain incident leads.
10. **Report supply-chain posture.** Track: percent of production artifacts signed and verified,
    provenance completeness (SLSA level achieved), key-rotation compliance, and verification-failure
    counts. Present as the software-supply-chain security metric set.

## Expected outputs
- Signing integrated into CI/CD for all artifact types, with HSM/KMS-protected keys.
- Transparency-logged signatures with SLSA-style provenance (source, commit, pipeline).
- Enforcement at consumption: admission controllers, package managers, update clients verifying.
- Key lifecycle, rotation, revocation, and emergency procedures documented.
- Monitoring on signing anomalies and supply-chain posture metrics.

## Pitfalls
- Signing without verification: the most common failure — signatures exist but nothing checks them.
  Enforcement points first.
- Keys on build workers: a compromised worker with the key signs malware legitimately. HSM/KMS with
  pipeline-identity-only access.
- No revocation plan: discovering key compromise without a distrust mechanism means choosing between
  outage and accepting forged artifacts.
- Dev keys reaching production: clearly separate dev and prod trust roots, and make prod verifiers
  reject dev signatures.
- Signing the artifact but not the SBOM/provenance: attackers can swap contents metadata; sign the
  full attestation bundle.

## References
- SLSA framework (supply-chain levels, provenance format)
- Sigstore documentation (cosign, Fulcio, Rekor)
- NIST SP 800-204D / EO 14028 guidance on software supply chain security
- NIST SP 800-53 SR family (supply chain risk management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
