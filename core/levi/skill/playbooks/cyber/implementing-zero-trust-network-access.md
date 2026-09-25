---
skill_id: cyber_implementing_zero_trust_network_access
name: Implementing Zero Trust Network Access
description: Replace implicit-trust network access with identity- and posture-based per-application access.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, ztna, network-access]
version: 1.0.0
---
## Purpose
This playbook implements Zero Trust Network Access: users and devices get brokered, per-application access based on identity, device posture, and risk — replacing VPN-style network-wide trust with least-privilege connectivity.

## When to use
- VPN grants broad network access once a user authenticates.
- Third parties and contractors need access to specific apps without network exposure.
- Supporting remote/hybrid work with consistent policy on and off the corporate network.

## Prerequisites
- Strong identity foundation: IdP with MFA (preferably phishing-resistant) and device inventory with compliance state.
- Application inventory: which internal apps need remote access, their protocols, and hosting locations.
- Pilot user group willing to validate the experience before broad rollout.

## Procedure
1. **Inventory applications and access patterns.** Catalog target apps, who needs them, from which devices and networks; this becomes the policy matrix.
2. **Select the architecture.** Choose agent-based vs. agentless (browser) access and a broker model (cloud-hosted, on-prem connector, or hybrid) fitting your app hosting.
3. **Define access policies.** Per application, specify required identity assurance, device posture (managed, patched, EDR healthy, encrypted), and contextual signals.
4. **Deploy connectors privately.** Place connectors near applications with outbound-only connectivity; applications are never exposed to the internet directly.
5. **Pilot, then migrate.** Run ZTNA alongside VPN for a pilot cohort; validate app compatibility (especially legacy protocols), then migrate groups and decommission VPN profiles.
6. **Log every access decision.** Ship allow/deny decisions with identity, device, and policy context to the SIEM for auditing and anomaly detection.
7. **Continuously re-evaluate.** Terminate sessions on posture or risk change (device compromise, impossible travel); access is a continuous decision, not a one-time grant.

8. **Handle third-party access.** Give contractors and vendors time-bound, app-scoped ZTNA access instead of VPN accounts that linger after the engagement ends.
9. **Decommission deliberately.** Only retire VPN profiles after verifying every migrated app works through ZTNA for every affected user cohort — then monitor for VPN re-enablement attempts.

## Expected outputs
- Application access matrix with per-app policy requirements.
- ZTNA deployment with connectors, policies, and logging operational.
- Migration plan retiring VPN access per user cohort.
- Example: a contractor receives 30-day access to exactly two internal applications, authenticated with MFA and a compliant device, with every session decision logged — and no VPN profile ever issued.

## Pitfalls
- Treating ZTNA as "VPN in the cloud" by granting overly broad application sets.
- Skipping device posture checks, reducing zero trust to username-and-password again.
- Legacy apps with hardcoded IPs or exotic protocols that break under brokering — test early.

- Device posture signals that can be spoofed by a rooted or jailbroken device reporting itself healthy; treat posture as one signal among many, not proof.
- Helpdesk-issued "temporary" policy exceptions during outages that never get revoked; track every exception with an expiry.

## References
- NIST SP 800-207, Zero Trust Architecture.
- CISA Zero Trust Maturity Model (cisa.gov/zero-trust-maturity-model).
- NIST SP 800-46 Rev. 2, Guide to Enterprise Telework and Remote Access Security.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
