---
skill_id: cyber_performing_ot_network_security_assessment
name: OT Network Security Assessment
description: Assess industrial control network segmentation, protocols, and access controls without disrupting operations.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, network, assessment]
version: 1.0.0
---

## Purpose
- Evaluate the security of OT networks with methods that respect process safety and availability.
- Map trust boundaries between enterprise, DMZ, and control zones and find where they leak.
- Give operations and engineering a remediation plan that fits maintenance realities.

## When to use
- When OT networks have grown organically and no current architecture review exists.
- Before or after connecting OT to enterprise systems, cloud historians, or remote access solutions.
- When risk assessments or insurers ask for evidence of OT network controls.
- After incidents elsewhere in the sector suggest similar network exposure.

## Prerequisites
- Written agreement with operations on what is in scope and what techniques are forbidden on live networks.
- Network diagrams, firewall rulesets, and an asset inventory for the control environment.
- A passive capture plan: span ports or taps identified, storage ready, and analysis tooling prepared.
- Knowledge of the industrial protocols in use (Modbus, DNP3, S7, EtherNet/IP, OPC) and their security properties.

## Procedure
1. Confirm safety constraints with operations and document the rules of engagement for every assessment activity.
2. Review architecture documents against reality: walk the network, verify firewall rules, and trace actual data flows.
3. Capture traffic passively from span ports or taps during representative operating periods.
4. Analyze captures for cleartext industrial protocols, unauthorized devices, and traffic crossing zone boundaries.
5. Inventory assets discovered on the wire and reconcile against the official inventory to find shadow OT.
6. Review remote access paths: vendor connections, cellular links, and jump hosts, checking authentication and logging.
7. Assess wireless in OT areas: access points, rogue devices, and encryption standards.
8. Evaluate network monitoring: what is logged, where logs go, and whether anyone reviews them.
9. Check backup network paths and out-of-band management for the control infrastructure itself.
10. Report findings with safety-aware remediation sequencing and compensating controls where patching is impossible.
11. Review time synchronization sources in OT, since manipulated NTP can undermine logs and safety functions.
12. Validate that safety instrumented systems are properly isolated from basic process control networks.

## Expected outputs
- A validated OT network architecture map with trust boundaries and data flows.
- Findings on segmentation, protocols, remote access, and monitoring with risk ratings.
- A remediation plan sequenced around operations and maintenance windows.

## Pitfalls
- Active scanning on fragile OT networks, which can crash legacy controllers; prefer passive methods.
- Assessing from diagrams alone without verifying what is actually on the wire.
- Recommending enterprise IT controls verbatim without adapting to OT constraints.
- Assuming a firewall rule review equals a segmentation assessment; verify actual traffic flows.

## References
- ISA TR84 guidance on safety system network separation concepts
- NIST SP 800-82 Guide to OT Security
- IEC 62443-3-3 system security requirements
- CISA ICS advisories and recommended practices
- ISA TR62443 guidance on network segmentation for IACS
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
