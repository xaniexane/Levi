---
skill_id: cyber_implementing_gcp_binary_authorization
name: GCP Binary Authorization
description: Enforce deploy-time binary authorization on GKE so only attested, trusted images run.
risk: low
permissions: []
requires_confirmation: false
tags: [gcp, supply-chain]
version: 1.0.0
---
## Purpose
Image scanning finds vulnerabilities, but nothing stops an unscanned, untested, or tampered image
from deploying — unless deployment itself enforces policy. GCP Binary Authorization is admission
control for GKE: images deploy only if they carry required attestations (vulnerability scan passed,
built by the trusted pipeline, QA signed off). This playbook implements it as the deploy-time gate
of the software supply chain.

## When to use
- Ensuring only vetted images deploy to GKE production clusters.
- Meeting supply-chain requirements (SLSA, EO 14028, customer attestations) on GCP.
- After incidents involving unauthorized or tampered image deployments.
- Before production GKE launches handling sensitive or regulated workloads.
- As the enforcement point for image scanning, code signing, and build provenance.

## Prerequisites
- GKE clusters with Binary Authorization enabled (per cluster — verify all production clusters).
- Attestors defined: who/what vouches for images (vulnerability scanner, build pipeline, QA) with
  their public keys (PGP or PKI).
- A signing/attestation workflow: notes in Artifact Analysis (Container Analysis) created by
  authorized attestors.
- Break-glass procedure: how to deploy urgently when attestation infrastructure is down (documented,
  dual-control, reviewed after).
- Image inventory: which images deploy to the clusters, from which registries.

## Procedure
1. **Enable Binary Authorization on clusters.** Turn it on for every production (and staging, for
   testing) GKE cluster. Start in dry-run/audit mode: violations logged but not blocked. Collect 1-2
   weeks of would-block data — this reveals every deployment path, including the ones you forgot
   (cronjobs, operators, manual kubectl).
2. **Define the attestation policy.** Specify required attestors per cluster/namespace: e.g.,
   production requires vuln-scan attestation + build-provenance attestation; staging requires
   build-provenance only. Write the policy as code (YAML), peer-reviewed, version-controlled.
3. **Set up attestors with proper keys.** Create attestors in Artifact Analysis; generate
   attestation key pairs with private keys held only by the attesting system (scanner service
   account, CI pipeline identity). Note: attestors vouch for images by signing attestations —
   protect those keys like signing keys.
4. **Build the attestation pipeline.** After image build and scanning: the scanner creates a
   vulnerability attestation (if policy passes), the CI system creates a build attestation
   (provenance: repo, commit, pipeline). Attestations attach to the image digest in Artifact
   Analysis. Fail closed: no attestation, no deploy.
5. **Handle existing and third-party images.** Inventory already-deployed images: backfill
   attestations after verifying them (scan + provenance check), or redeploy from attested builds.
   Third-party images (operators, sidecars): establish an attestation process (scan them yourself,
   attest internally) — no unattested exceptions for "vendor images."
6. **Enforce and monitor.** Switch from dry-run to enforce. Monitor: dry-run violation logs (now
   blocks), attestation creation failures (pipeline issues), and enforcement bypass attempts. Alert
   on policy changes and break-glass usage.
7. **Define break-glass narrowly.** Emergency deployments without attestations: require dual
   approval, time-bound policy exemption, automatic post-incident review, and mandatory retroactive
   attestation or redeployment. Break-glass is for incidents, not convenience — audit every use.
8. **Integrate with image promotion.** Tie attestation to the promotion flow: dev → staging → prod,
   with each stage's attestations gating the next. An image can't reach prod without accumulating
   the required attestations — the pipeline enforces the journey, Binary Authorization enforces the
   destination.
9. **Test the enforcement.** Attempt: deploying an unsigned image (must be denied), deploying with a
   forged attestation (must fail signature verification), and deploying during attestation-service
   outage (must fail closed or follow the break-glass path). Document as control evidence.
10. **Review and report.** Quarterly: attestor key rotation, policy review (are required
    attestations still the right ones?), exemption/break-glass audit, and coverage (percent of
    workloads under enforcement). Report supply-chain posture: attested-deploy percent, policy
    violations blocked, attestation pipeline health.

## Expected outputs
- Binary Authorization enforcing attestation policies on all production GKE clusters.
- Attestors (scanner, build, QA) with protected keys and an automated attestation pipeline.
- Backfilled/third-party image handling with no unattested exceptions.
- Break-glass procedure with dual control and mandatory review.
- Enforcement tests, key rotation, and supply-chain posture reporting.

## Pitfalls
- Enforcing without dry-run: unknown deployment paths (operators, cronjobs, GitOps edge cases)
  break. Audit first.
- Attestor keys poorly protected: a compromised attestor key forges "scanned and safe" for anything.
  HSM/service-account protection, rotation.
- Third-party image exceptions: "vendor images can't be attested" becomes the permanent bypass. Scan
  and attest them yourself.
- Break-glass as routine: every emergency exemption needs post-review and retroactive compliance, or
  it becomes the normal path.
- Policy drift: clusters created without Binary Authorization (new projects, dev clusters promoted
  to prod). Enforce via organization policy that new clusters enable it.

## References
- Google Cloud Binary Authorization documentation (policies, attestors, dry-run mode)
- Google Cloud Artifact Analysis documentation (attestations, notes)
- SLSA framework (provenance and attestation concepts)
- NIST SP 800-53 SR-11, CM-14 (supply chain, signed components)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
