---
skill_id: cyber_implementing_image_provenance_verification_with_cosign
name: Implementing Image Provenance Verification with Cosign
description: Verify container image signatures and attestations with Sigstore cosign and enforce signature admission policies so only trusted images run.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, containers, signing, kubernetes]
version: 1.0.0
---
## Purpose

Ensure every container image admitted to your clusters was built by your pipeline and has not been tampered with, using Sigstore's cosign for signing and verification. Signatures cover the image digest; attestations (SLSA provenance, SBOMs, vulnerability scan results) bind build metadata to the artifact, and an admission controller rejects anything unverified — closing the gap that lets a compromised registry or a typosquatted image deploy malicious code.

## When to use

- Hardening Kubernetes admission so only pipeline-signed images deploy.
- Meeting supply-chain requirements (SLSA, EO 14028, PCI DSS 4.0 software integrity expectations).
- Detecting registry compromise or image tampering between build and deploy.
- Verifying third-party or base images before promoting them to production registries.
- Building SBOM-attested, provenance-verified release pipelines.

## Prerequisites

- A container registry you control for production images (do not verify-then-pull from public registries at deploy time without pinning digests).
- CI/CD pipeline with a defined build step where signing occurs — sign at build, verify at deploy, never the reverse.
- Decision on key management: keyless signing via Sigstore Fulcio (OIDC identity-bound, short-lived certs) or long-lived keys in a KMS/HSM. Keyless is the modern default; long-lived keys need rotation and revocation procedures.
- An admission enforcement point: Sigstore policy-controller, Kyverno, or OPA Gatekeeper with the cosign verification logic.
- Rekor transparency log access (public instance or your own) for signature auditability.

## Procedure

1. **Choose the signing trust model.** Prefer keyless: the CI job authenticates with OIDC (e.g., GitHub Actions identity), Fulcio issues a short-lived certificate binding the signature to the workload identity, and Rekor records it. Document the exact identities (repo, workflow, branch protections) allowed to sign — anyone who can run that workflow can sign.
2. **Sign images in the pipeline.** After building and pushing, sign by digest (never by mutable tag):
   ```bash
   cosign sign --yes <registry>/<image>@<digest>
   ```
   Pin digests everywhere downstream; tags are pointers, digests are identities.
3. **Attach attestations.** Generate and attach SLSA provenance and SBOM attestations at build time:
   ```bash
   cosign attest --yes --predicate sbom.spdx.json --type spdx <registry>/<image>@<digest>
   ```
   Include vulnerability scan results as attestations so admission policy can gate on scan age and severity thresholds.
4. **Verify manually before enforcing.** Test verification exactly as the cluster will perform it:
   ```bash
   cosign verify --certificate-identity-regexp 'https://github.com/<org>/.*' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     <registry>/<image>@<digest>
   cosign verify-attestation --type spdx --predicate <policy> <registry>/<image>@<digest>
   ```
   Confirm failures on tampered digests, wrong identities, and expired certificates.
5. **Enforce at admission.** Deploy policy-controller (or equivalent) with a ClusterImagePolicy requiring valid signatures from your identities on all namespaces except explicitly exempted break-glass ones. Start in warn/audit mode, review violations, then switch to enforce.
6. **Handle the exceptions deliberately.** Maintain a minimal, time-boxed allowlist for emergency images and third-party images you cannot sign yourself (verify vendor signatures instead, e.g., Chainguard or distroless publishers). Every exception gets an owner and an expiry.
7. **Monitor the transparency log.** Alert on signatures from unexpected identities or signing events outside pipeline runs — a valid signature from an unexpected identity is a pipeline-compromise indicator, not a green light.
8. **Rotate and revoke.** For KMS-backed keys, rotate on schedule and test revocation. For keyless, rotate by tightening the allowed identity set and expiring old trust roots; re-sign or re-verify images after trust changes.

## Expected outputs

- Pipeline jobs signing images by digest with keyless or KMS-backed identities.
- SBOM and provenance attestations attached to production images.
- ClusterImagePolicy (or equivalent) enforcing signature verification in enforce mode.
- Exception allowlist with owners and expiries.
- Rekor monitoring alerts for anomalous signing activity.

## Pitfalls

- **Verifying tags instead of digests.** A signature on `latest` is meaningless after the tag moves. Always sign and verify the digest.
- **Signing in the wrong stage.** Signing after vulnerability scanning but before final image assembly leaves a gap; sign the exact artifact that ships, as the last build step.
- **Overly broad certificate identities.** `--certificate-identity-regexp '.*'` trusts any Fulcio signer on earth. Constrain to your org's OIDC identities.
- **Break-glass namespaces without alerting.** Exempted namespaces become the deployment path of choice for attackers and lazy engineers alike; alert on every use.
- **Ignoring attestation freshness.** A valid signature on a six-month-old image with unpatched CVEs passes naive verification; gate on attested scan age and severity too.

## References

- Sigstore cosign documentation — https://docs.sigstore.dev/cosign/signing/overview/
- SLSA framework (supply-chain levels) — https://slsa.dev/
- NIST SP 800-204D (strategies for securing container supply chains) and EO 14028 software supply chain guidance — https://csrc.nist.gov/
- MITRE ATT&CK T1190 / T1554-adjacent supply-chain considerations — https://attack.mitre.org/techniques/T1190/
