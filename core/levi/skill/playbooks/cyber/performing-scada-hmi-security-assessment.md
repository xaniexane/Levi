---
skill_id: cyber_performing_scada_hmi_security_assessment
name: SCADA HMI Security Assessment
description: Assess SCADA human-machine interface systems for vulnerabilities and misconfigurations without disrupting operations.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, scada, hmi]
version: 1.0.0
---

## Purpose
- Evaluate the security of HMI systems that operators depend on for process visibility and control.
- Find the weak authentication, unpatched software, and network exposure common on HMI stations.
- Recommend hardening that preserves operator usability and process safety.

## When to use
- During OT security assessments that include control-room and field HMI systems.
- When HMI platforms are due for upgrade or vendor support is ending.
- After incidents involving HMI compromise or unauthorized process changes.
- When remote HMI access is introduced for operators or vendors.

## Prerequisites
- Operations approval with explicit rules for any interaction with live HMI systems.
- An inventory of HMI platforms, versions, and their roles in the process.
- Network diagrams showing HMI placement relative to PLCs, historians, and enterprise networks.
- A passive-first methodology: observe and review configurations before any active checks.

## Procedure
1. Confirm scope and safety constraints with operations; default to read-only review of live systems.
2. Inventory HMI stations: OS versions, HMI software versions, and patch levels.
3. Review authentication: shared operator accounts, weak passwords, auto-logon, and unattended unlocked sessions.
4. Check network exposure: which networks can reach the HMI, and whether remote access paths are controlled.
5. Assess the underlying OS: unpatched Windows builds, unnecessary services, and missing endpoint protection.
6. Review HMI application security: project file protections, script execution, and alarm management integrity.
7. Check backup and recovery for HMI configurations and graphics; test restore in a lab, not production.
8. Evaluate physical security of HMI stations: USB ports, console access, and control-room entry controls.
9. Review change management for HMI modifications: who can change graphics, setpoints, or alarm limits.
10. Deliver findings with safety-aware remediation sequenced around operations.

## Expected outputs
- An HMI security assessment with findings ranked by operational risk.
- Hardening recommendations that preserve usability and safety.
- Backup and recovery validation results.
- A control-room security baseline document for future HMI deployments.
- Operator training updates covering the social and physical findings.

## Pitfalls
- Making configuration changes on a live HMI during the assessment; assess, do not fix, without approval.
- Recommending lockout policies that could lock operators out during process upsets.
- Ignoring the human factor: the most secure HMI fails if operators share one password.
- Assessing the HMI software while ignoring the Windows host underneath it.

## References
- NIST SP 800-82 Rev 3 for current OT guidance
- NIST SP 800-82 Guide to OT Security
- CISA ICS advisories for HMI platforms
- IEC 62443-3-3 system security requirements
- Vendor hardening guides for the HMI platforms in use
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
