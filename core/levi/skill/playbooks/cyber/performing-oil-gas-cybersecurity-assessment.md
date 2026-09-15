---
skill_id: cyber_performing_oil_gas_cybersecurity_assessment
name: Oil and Gas Cybersecurity Assessment
description: Assess IT and OT cybersecurity posture across upstream, midstream, and downstream oil and gas operations.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, energy, assessment]
version: 1.0.0
---

## Purpose
- Evaluate security across the converged IT and OT environments typical of oil and gas operators.
- Identify risks to safety, production continuity, and environmental compliance from cyber threats.
- Align findings with energy-sector guidance so remediation fits industry expectations and regulations.

## When to use
- When an operator needs a sector-specific view of cyber risk beyond a generic IT assessment.
- Before connecting new OT assets or remote sites to corporate networks.
- When regulators, insurers, or joint-venture partners request evidence of due diligence.
- After incidents in the sector suggest similar exposure in your own environment.

## Prerequisites
- Engagement scope agreed with operations leadership, with safety constraints documented for any OT interaction.
- Network diagrams covering corporate IT, DMZ, and OT zones including remote wellheads, pipelines, and terminals.
- Inventory of control systems: SCADA, DCS, PLCs, RTUs, and historians.
- Relevant standards: API, NIST, and applicable national regulations for the operating regions.

## Procedure
1. Confirm scope and safety rules with operations: no active scanning or testing on live control networks without explicit approval.
2. Map the IT/OT boundary: firewalls, data diodes, jump hosts, and every path between corporate and control networks.
3. Review remote access into OT: vendor VPNs, cellular links to wellheads, and third-party maintenance connections.
4. Assess identity and access controls for control-system accounts, shared operator logins, and vendor credentials.
5. Evaluate patching and vulnerability management for OT assets within maintenance-window realities.
6. Review backup and recovery for SCADA servers, historians, and PLC configurations, including tested restore procedures.
7. Examine incident response plans for scenarios like pipeline SCADA compromise or ransomware reaching the DMZ.
8. Assess supply-chain risk for control-system vendors and remote-site equipment.
9. Check physical security at remote unmanned sites: enclosures, tamper evidence, and environmental monitoring.
10. Deliver findings ranked by safety and production impact, with remediation sequenced around operational constraints.
11. Review emergency shutdown and safety instrumented systems for cyber-induced common-cause failure scenarios.
12. Assess third-party pipeline scheduling and nomination systems that bridge business and OT networks.

## Expected outputs
- A sector-specific risk assessment covering IT, OT, and their interconnections.
- Findings ranked by safety, environmental, and production impact.
- A remediation roadmap that respects maintenance windows and operational realities.

## Pitfalls
- Applying IT assessment techniques to live control networks and causing process disruption.
- Ignoring remote unmanned sites, which are often the weakest link in oil and gas estates.
- Writing findings that operations cannot act on because they ignore maintenance and safety constraints.
- Overlooking safety instrumented systems, which need cyber assessment without compromising their independence.

## References
- IEC 61511 functional safety standard as context for SIS cyber reviews
- API Standard 1164 on pipeline SCADA security
- NIST SP 800-82 Guide to OT Security
- CISA guidance for the energy sector and TSA pipeline security directives
- IEC 62443 series on industrial automation and control systems security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
