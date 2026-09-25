---
skill_id: cyber_performing_vlan_hopping_attack
name: VLAN Hopping Detection and Prevention
description: Detect VLAN hopping attempts and harden switch configurations to enforce network segmentation.
risk: low
permissions: []
requires_confirmation: false
tags: [network, vlan, hardening]
version: 1.0.0
---

## Purpose
- This playbook is defensive: detect VLAN hopping, assess segmentation effectiveness, and harden switches. It does not cover attacking networks without authorization.
- Teach analysts to recognize double-tagging and switch-spoofing indicators.
- Validate that VLAN segmentation actually isolates traffic as designed.
- Harden switch configurations against the classic hopping techniques.

## When to use
- During network security assessments of segmented environments.
- When investigating suspected lateral movement between VLANs.
- When deploying or auditing 802.1Q segmentation for compliance.
- After changes to switch configurations that could weaken segmentation.

## Prerequisites
- Written authorization for any active assessment of segmentation.
- Network diagrams with VLAN assignments and trunk port inventories.
- Switch configuration access for review and monitoring capabilities.
- An isolated lab for validating attack techniques safely if needed.

## Procedure
1. Review switch configurations: trunk ports explicitly defined, native VLANs assigned to unused IDs, DTP disabled.
2. Verify access ports cannot negotiate trunks: set port modes explicitly and disable dynamic trunking.
3. Check for double-tagging exposure: ensure the native VLAN on trunks carries no sensitive traffic.
4. Monitor for attack indicators: DTP negotiation attempts, unexpected 802.1Q tags, and CAM table anomalies.
5. Assess private VLAN or ACL controls that provide defense in depth beyond tagging.
6. In authorized lab testing only, validate that hopping attempts fail against the hardened configuration.
7. Review voice and data VLAN separation on access ports.
8. Check that management VLANs are isolated from user VLANs with no routable shortcuts.
9. Log and alert on trunk-port state changes and unexpected tagged traffic on access ports.
10. Document the hardened baseline and audit switch configs against it regularly.
11. Include VLAN segmentation in network change control so new trunks do not appear unreviewed.
12. Report findings with the segmentation impact of each gap.

## Expected outputs
- A switch hardening assessment against the VLAN baseline.
- Monitoring coverage for hopping indicators.
- A validated segmentation posture with audit evidence.
- A network segmentation test plan for recurring audits.
- Configuration compliance checks in the network automation pipeline.

## Pitfalls
- Assuming VLANs equal security; without hardening, hopping defeats the segmentation.
- Leaving DTP enabled, which lets any connected device negotiate a trunk.
- Testing hopping techniques on production networks; use the lab.
- Forgetting wireless bridges that can bypass VLAN segmentation entirely.

## References
- NIST SP 800-41 Guidelines on Firewalls and Firewall Policy
- Cisco guidance on VLAN security best practices
- NIST SP 800-53 controls on boundary protection
- SANS network security assessment resources
- IEEE 802.1Q standard for VLAN tagging
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
