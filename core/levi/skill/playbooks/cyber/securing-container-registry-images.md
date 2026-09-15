---
skill_id: cyber_securing_container_registry_images
name: Securing Container Registry Images
description: Harden container registries: sign images, scan on push, enforce immutable tags, and control retention.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, registry, supply-chain]
version: 1.0.0
---
## Purpose
The registry is the choke point where malicious or vulnerable images can be stopped before deployment. This playbook hardens registry operations in a vendor-neutral way: image signing and verification, push-time scanning, immutable tags, access control, and lifecycle retention.

## When to use
- Standing up or hardening an internal container registry.
- Supply-chain security program requiring signed, scanned images.
- After discovering vulnerable or tampered images in the registry.
- Compliance requiring provenance for deployed artifacts.

## Prerequisites
- Registry admin access and an inventory of repositories and consumers.
- Signing tooling (Cosign/Sigstore) and a key/trust-root strategy.
- Vulnerability scanner integrated or integrable with the registry.
- Deployment pipeline hooks where signature verification can be enforced.

## Procedure
1. Enable authentication on all repositories; remove anonymous pull except for explicitly public ones.
2. Turn on push-time vulnerability scanning; quarantine or block images with critical CVEs per policy.
3. Sign images at build time with Cosign; store signatures and attestations alongside artifacts.
4. Enforce signature verification in deployment (admission controller or pipeline gate); unsigned images do not deploy.
5. Make production tags immutable so a deployed digest cannot be overwritten by a later push.
6. Apply RBAC: separate push, pull, and admin roles per project/team; use short-lived tokens for CI.
7. Set retention and cleanup policies to remove stale, unscanned, or superseded images.
8. Monitor registry audit logs for anomalous pulls, pushes, and permission changes.
9. Quarantine newly pushed images until scanning completes; block pulls of unscanned images.
10. Coordinate retention policies with digest pinning so garbage collection does not break deployments.
11. Require provenance attestations for base images, not just application images.

## Expected outputs
- Registry hardening checklist with configuration evidence.
- Signing and verification workflow integrated into build and deploy.
- Retention, RBAC, and monitoring configuration.
- Quarantine policy and enforcement evidence.
- Retention-vs-pinning coordination record.
- Base-image provenance requirements.

## Pitfalls
- Mutable `latest` tags make incident forensics unreliable; pin digests in production.
- Signature verification only in CI is bypassable; enforce at admission too.
- Key management for signing is the weak link; use a managed trust root (Sigstore) or HSM-backed keys.
- Scanning on push without blocking just creates unread reports; connect results to gates.
- Digest pinning breaks when registries garbage-collect untagged digests; coordinate retention.
- Pull-through cache registries can serve stale or tampered upstreams; verify the cache.
- Quarantine without developer feedback just creates delays; surface scan results in the pipeline.
- Registry garbage collection during incidents can destroy evidence; pause retention jobs when investigating.

## References
- NIST SP 800-190, Application Container Security Guide.
- Sigstore/Cosign documentation.
- SLSA framework (slsa.dev).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
