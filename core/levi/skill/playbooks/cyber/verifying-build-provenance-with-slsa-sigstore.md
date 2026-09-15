---
skill_id: cyber_verifying_build_provenance_with_slsa_sigstore
name: Verifying Build Provenance with SLSA and Sigstore
description: Verify software build provenance using SLSA attestations and Sigstore signing before trusting artifacts.
risk: info
permissions: []
requires_confirmation: false
tags: [supply-chain, slsa, sigstore]
version: 1.0.0
---
## Purpose
Build provenance answers 'where did this artifact really come from and how was it built?' SLSA defines the provenance levels; Sigstore provides the signing and transparency infrastructure. This playbook verifies provenance as a consumer: checking attestations and signatures before deploying artifacts, and enforcing verification in the pipeline.

## When to use
- Adopting artifacts from third-party or open-source suppliers.
- Enforcing supply-chain policy before production deployment.
- Investigating a suspected build-system compromise.
- Compliance requiring software provenance evidence.

## Prerequisites
- Artifacts with SLSA provenance attestations and Sigstore signatures.
- Verification tooling (slsa-verifier, Cosign) in the pipeline.
- Policy defining required SLSA level and trusted builders per artifact source.
- Transparency log access for signature verification.

## Procedure
1. Inventory the artifacts requiring provenance verification and their expected builders.
2. Fetch the SLSA provenance attestation alongside each artifact.
3. Verify the attestation signature with Cosign against the expected identity (OIDC issuer/subject of the builder).
4. Check the transparency log inclusion proof so the signature cannot be backdated or hidden.
5. Validate provenance contents: builder ID matches policy, source repo and commit match expectations, and the SLSA level meets the minimum.
6. Enforce verification as a deployment gate; unverified or mismatched artifacts do not deploy.
7. Alert on verification failures and treat repeated failures as a potential supplier compromise.
8. Record verification results as audit evidence tied to each deployed artifact version.
9. Require provenance for base images and build tooling too, not just application artifacts.
10. Monitor OIDC issuer anomalies; builder-identity spoofing is the advanced threat here.
11. Publish your own provenance so downstream consumers can verify your builds.

## Expected outputs
- Provenance verification policy: required levels and trusted builders.
- Deployment gate configuration with verification steps.
- Verification audit log per artifact version.
- Provenance requirements extended to base images and tooling.
- OIDC issuer monitoring rules.
- Published provenance for your own artifacts.

## Pitfalls
- Verifying signatures without checking the identity they were issued to is theater; bind to expected builders.
- Provenance only covers the build; source-code compromise upstream still needs code review and scanning.
- Keyless Sigstore signing depends on OIDC issuer trust; understand the trust root you rely on.
- Not all suppliers publish provenance yet; have a migration plan with deadlines, not indefinite exceptions.
- Builder identity spoofing via compromised OIDC is the advanced threat; monitor issuer anomalies.
- Provenance verification at deploy time needs the verifier in the critical path; test failover.
- Hermetic build claims need verification; non-hermetic builds weaken provenance guarantees.
- Provenance for infrastructure-as-code artifacts is often forgotten; include Terraform modules and images.

## References
- SLSA specification (slsa.dev).
- Sigstore documentation (sigstore.dev).
- NIST SP 800-218 (SSDF) for secure software development practices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
