---
skill_id: cyber_implementing_zero_trust_with_beyondcorp
name: Implementing Zero Trust with the BeyondCorp Model
description: Apply Google's BeyondCorp principles to shift access control from network to identity and device.
risk: info
permissions: []
requires_confirmation: false
tags: [zero-trust, beyondcorp, architecture]
version: 1.0.0
---
## Purpose
This playbook applies the BeyondCorp model — access based on device and user identity rather than network location — as an architecture pattern you can implement with any vendor stack, not as a Google product deployment.

## When to use
- Designing a zero-trust program and needing a proven reference model.
- Justifying the shift from perimeter security to identity-centric controls.
- Evaluating vendor architectures against BeyondCorp's maturity tiers.

## Prerequisites
- Authoritative device inventory with a trust tiering concept (managed/corporate vs. personal).
- Identity provider capable of strong authentication and rich context signals.
- Executive understanding that this is a multi-quarter architecture program, not a product purchase.

## Procedure
1. **Establish the device inventory.** Every device that accesses corporate resources must be known, with ownership, OS, patch, and encryption state — this is the foundation everything else rests on.
2. **Build the trust inference pipeline.** Aggregate signals (device certificates, patch state, EDR health, user behavior) into a per-request trust assessment.
3. **Deploy the access proxy tier.** Front applications with an authenticating proxy that enforces policy per request; no application is reachable without passing the proxy.
4. **Define tiered access policies.** Map application sensitivity to required trust levels: low-trust devices get only low-sensitivity apps; privileged workflows require managed, healthy devices and step-up auth.
5. **Migrate applications in waves.** Start with web apps (easiest to proxy), then SSH/RDP equivalents, then legacy protocols; keep the VPN shrinking as coverage grows.
6. **Handle exceptions explicitly.** Document break-glass and incompatible workflows with compensating controls and sunset dates.
7. **Measure the perimeter shrink.** Track the percentage of access decisions made at the proxy vs. the legacy VPN, and the reduction in network-trusted zones.

8. **Address non-web protocols.** Plan explicitly for SSH, RDP, database, and legacy protocols; BeyondCorp-style proxying must cover them or the VPN never dies.
9. **Publish the model internally.** A one-page diagram of "how access decisions work here" aligns engineering, support, and users on the new mental model.

## Expected outputs
- Architecture document mapping BeyondCorp components to your implemented controls.
- Device trust tiering policy and per-application access requirements.
- Migration waves with success criteria and rollback plans.
- Example: after wave two, 80% of workforce application access flows through the access proxy with per-request policy checks, and the legacy VPN serves only the remaining legacy-protocol exceptions.

## Pitfalls
- Buying products labeled "zero trust" without the device inventory and policy engine underneath.
- Proxying authentication but leaving backdoor network paths to the applications.
- Underestimating the change management: users experience this as a new way of working.

- Declaring victory when the proxy is deployed but applications remain reachable via legacy network paths; verify every bypass is closed.
- Trust inference based on signals the user controls (self-reported device health); weight signals by their resistance to spoofing.

## References
- Google BeyondCorp research papers (research.google/pubs — "BeyondCorp" series).
- NIST SP 800-207, Zero Trust Architecture.
- "BeyondCorp: A New Approach to Enterprise Security" (;login: magazine, USENIX) — original design rationale.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
