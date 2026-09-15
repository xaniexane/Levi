---
skill_id: cyber_implementing_zero_trust_in_cloud
name: Implementing Zero Trust in Cloud Environments
description: Architect zero-trust controls across cloud identity, network, workload, and data planes.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, cloud-security, architecture]
version: 1.0.0
---
## Purpose
This playbook translates zero-trust principles into concrete cloud architecture: identity-centric access, micro-segmented networks, workload identity, encrypted data, and continuous monitoring — for AWS, Azure, or GCP.

## When to use
- Cloud environments rely on flat networks and long-lived credentials.
- Migrating workloads to cloud without rethinking the security model.
- Building a cloud landing zone with security as a design constraint.

## Prerequisites
- Cloud organization structure with separated management, security, and workload accounts/subscriptions.
- Centralized identity (IdP federated to the cloud provider) with MFA enforced.
- Logging baseline: cloud control-plane audit logs flowing to a security account.

## Procedure
1. **Start with identity as the perimeter.** Federate human and workload access through the IdP; eliminate long-lived access keys in favor of short-lived, assumed roles with MFA conditions.
2. **Segment the network.** Design VPC/VNet tiers (public, private, data), deny-by-default security groups, and private connectivity; avoid flat networks where one compromise reaches everything.
3. **Give workloads identity.** Use cloud-native workload identity (IAM roles for service accounts, managed identities) so applications authenticate without embedded secrets.
4. **Encrypt and control data.** Enforce encryption at rest with customer-managed keys for sensitive data, TLS everywhere in transit, and bucket/storage policies that deny public access by default.
5. **Codify guardrails.** Deploy SCPs, Azure Policy, or Organization Policies that prevent known-bad configurations (public storage, unencrypted databases, overly broad IAM).
6. **Monitor the control plane.** Alert on IAM changes, privilege grants, unusual API calls, and guardrail modifications — the cloud control plane is the new domain controller.
7. **Verify continuously.** Run CSPM and periodic architecture reviews; treat drift from the approved design as a finding, not a preference.

8. **Secure the CI/CD pipeline.** Treat deployment pipelines as tier-0: OIDC-based cloud auth, protected branches, signed artifacts, and no long-lived cloud keys in CI secrets.
9. **Run game days.** Periodically simulate control-plane compromise (revoked keys, malicious policy change) to verify detection and recovery actually work.

## Expected outputs
- Reference architecture documenting identity, network, and data controls per environment.
- Codified preventive guardrails with drift detection.
- Control-plane alerting mapped to cloud threat techniques.
- Example: an SCP denies S3 public-access changes account-wide while CloudTrail alerts fire within minutes if anyone attempts to modify the guardrail itself.

## Pitfalls
- Lifting and shifting the flat on-prem network into the cloud.
- Long-lived keys committed to code or CI that outlive their creators.
- Guardrails that exist but nobody monitors for violations or tampering.

- Assuming the cloud provider's default encryption means your keys are under your control; verify key ownership and rotation for regulated data.
- Network security groups that allow all outbound traffic by default; egress filtering is part of zero trust, not just ingress.

## References
- NIST SP 800-207, Zero Trust Architecture.
- CISA Zero Trust Maturity Model (cisa.gov/zero-trust-maturity-model).
- Cloud provider security best-practice docs (AWS Well-Architected Security Pillar; Microsoft Cloud Adoption Framework; Google Cloud Architecture Framework).
- CIS Benchmarks for cloud platforms (cisecurity.org) — configuration baselines.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
