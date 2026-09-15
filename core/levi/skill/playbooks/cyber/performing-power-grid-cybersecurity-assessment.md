---
skill_id: cyber_performing_power_grid_cybersecurity_assessment
name: Power Grid Cybersecurity Assessment
description: Assess cybersecurity across power grid generation, transmission, and distribution OT and IT environments.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, energy, grid]
version: 1.0.0
---

## Purpose
- Evaluate cyber risk to grid reliability across generation, transmission, and distribution systems.
- Align assessment with NERC CIP and other grid-specific regulatory expectations.
- Prioritize remediation by reliability impact so the most critical weaknesses are fixed first.

## When to use
- When a utility needs a comprehensive view of cyber risk to bulk electric system reliability.
- Before NERC CIP audits, to find and fix gaps proactively.
- After sector incidents or alerts suggest similar exposure.
- When integrating renewables, DERs, or new control centers that change the attack surface.

## Prerequisites
- Scope agreement with operations covering EMS, SCADA, substations, and supporting IT, with safety constraints documented.
- Knowledge of NERC CIP standards applicable to the registered entity's assets.
- Network diagrams, asset inventories, and existing compliance evidence.
- A safety-first assessment methodology with no active testing on live control systems without explicit approval.

## Procedure
1. Confirm scope, safety rules, and the NERC CIP standards in scope with compliance and operations leadership.
2. Map the electronic security perimeters: control centers, substations, generation plants, and their interconnections.
3. Review access management for BES cyber systems: account provisioning, shared accounts, and vendor access.
4. Assess system security management: patching, malicious-code prevention, and security event monitoring within CIP timelines.
5. Evaluate incident response and recovery plans for grid cyber scenarios, including backup control center capabilities.
6. Review supply-chain risk management for BES cyber systems per CIP-013 requirements.
7. Examine physical security of critical substations and control centers as it relates to cyber access.
8. Assess change management and baseline configuration practices for control system assets.
9. Check logging and alerting coverage: what security events are collected, retained, and reviewed.
10. Deliver findings mapped to CIP requirements and reliability impact, with remediation sequenced around operations.

## Expected outputs
- A grid cybersecurity assessment mapped to NERC CIP and reliability risk.
- Prioritized findings with remediation plans that respect operational constraints.
- Evidence packages useful for audit preparation.
- A reliability-weighted risk register linking each finding to grid impact.
- Tabletop exercise scenarios derived from the highest-risk findings.

## Pitfalls
- Assessing CIP compliance on paper without verifying the controls actually work.
- Overlooking distribution and DER assets that fall outside CIP but still affect reliability.
- Recommending changes that conflict with real-time operations requirements.

## References
- DOE Cybersecurity Capability Maturity Model (C2M2)
- NERC CIP standards
- NIST SP 800-82 Guide to OT Security
- NISTIR 7628 Guidelines for Smart Grid Cybersecurity
- CISA and DOE guidance for the electricity subsector
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
