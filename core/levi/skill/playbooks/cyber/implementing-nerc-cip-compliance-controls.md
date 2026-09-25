---
skill_id: cyber_implementing_nerc_cip_compliance_controls
name: Implementing NERC CIP Compliance Controls
description: Implement the NERC Critical Infrastructure Protection standards — BES asset categorization, ESP/PSP boundaries, access management, and audit-ready evidence.
risk: info
permissions: []
requires_confirmation: false
tags: [compliance, ics, ot, nerc-cip]
version: 1.0.0
---
## Purpose

Build a defensible NERC CIP compliance program for Bulk Electric System (BES) cyber systems: categorize assets, define Electronic Security Perimeters (ESPs) and Physical Security Perimeters (PSPs), implement the personnel, access, and system-security controls across CIP-002 through CIP-014, and produce the evidence auditors expect. Compliance here is not paperwork — CIP violations carry fines up to roughly $1M+ per day per violation, and the controls genuinely reduce grid risk.

## When to use

- Operating BES cyber systems as a registered entity (balancing authority, generator owner/operator, transmission owner/operator, etc.).
- Preparing for a NERC audit, spot check, or self-certification.
- Integrating newly acquired generation or transmission assets into the CIP program.
- Responding to a CIP violation or audit finding with corrective action plans.
- Aligning OT security investments with the standards the auditors will test.

## Prerequisites

- Registered-entity status determination and applicability analysis (which facilities, voltage levels, and generation thresholds bring assets into scope).
- Complete BES Cyber System categorization draft per CIP-002 (High, Medium, Low impact, or non-applicable) with methodology documented.
- Asset inventory with network diagrams showing routable connectivity — the ESP boundary definition depends on it.
- Named CIP Senior Manager and delegated authorities; accountability is an explicit requirement.
- Access to the current CIP standards text (CIP-002 through CIP-014) from NERC.

## Procedure

1. **Categorize BES Cyber Systems (CIP-002).** Apply the bright-line criteria to identify High and Medium impact systems (control centers, large generation, critical transmission substations), then evaluate Low-impact systems. Document the methodology and every categorization decision — auditors start here, and miscategorization invalidates everything downstream.
2. **Define ESPs and PSPs (CIP-005, CIP-006).** Draw Electronic Security Perimeters around High/Medium impact systems at every routable-protocol boundary; define Physical Security Perimeters controlling physical access to them. Every ESP access point gets inbound/outbound filtering, authentication where technically feasible, and monitoring. Document Interactive Remote Access paths explicitly — vendor remote access into the ESP is the most scrutinized conduit in the industry.
3. **Implement personnel and training controls (CIP-004).** Personnel risk assessments (background checks) before granting electronic or physical access, role-based security training with annual refreshers, and access reviews. Maintain the access lists as living documents — stale access lists are among the most common audit findings.
4. **Manage electronic and physical access (CIP-005, CIP-006, CIP-007).** Enforce least-privilege electronic access with unique credentials, manage shared accounts where technically feasible, control physical access with logging and escorting, and implement CIP-007 system security management: malicious-code prevention, security patch management with 35-day evaluation cycles, and ports/services hardening on every BES Cyber System.
5. **Build incident response and recovery (CIP-008, CIP-009).** Maintain CIP-specific incident response plans (recognize, classify, respond, notify the E-ISAC within required timeframes), test them annually with lessons-learned documentation, and keep recovery plans with tested backups for High/Medium systems.
6. **Control changes and configurations (CIP-010).** Baseline configurations for High/Medium systems, authorize and test changes before production, monitor for unauthorized changes, and assess vulnerability (active or paper) on the required cadence. Untracked changes to relay settings or EMS configurations are both a reliability and a compliance risk.
7. **Protect information and supply chain (CIP-011, CIP-013).** Classify and protect BES Cyber System Information (BCSI) with handling procedures, and implement supply-chain risk management: vendor security assessments, procurement language, and verification of software/firmware integrity for High/Medium systems.
8. **Maintain audit-ready evidence continuously.** For every requirement, keep dated evidence: policies, procedures, logs, review records, training completions, test results. Run internal mock audits annually against the RSAWs (Reliability Standard Audit Worksheets) — the audit tests evidence of implementation, not the existence of policy binders.

## Expected outputs

- CIP-002 categorization records with documented methodology.
- ESP/PSP diagrams with access-point inventories and monitoring.
- Personnel, training, and access-review records (CIP-004).
- Patch, malware, ports/services, and change-management evidence (CIP-007/010).
- Tested incident response and recovery plans (CIP-008/009); supply-chain program (CIP-013); BCSI protections (CIP-011).
- Mock-audit results mapped to RSAWs with remediation tracking.

## Pitfalls

- **Miscategorization.** Under-categorizing to reduce scope is the fastest path to a major violation when auditors disagree. Document the analysis; when in doubt, categorize up and note why.
- **Unmanaged vendor remote access.** Third-party connections into the ESP without intermediate systems, MFA, and session monitoring draw findings and represent real attack paths (see supply-chain compromises in the sector).
- **Evidence gaps.** Controls implemented but not evidenced fail audits. If it isn't dated, signed, and retrievable, it didn't happen.
- **Treating Low-impact as no-impact.** Low-impact systems still carry CIP-003 requirements (policies, awareness, physical/electronic access controls, incident response). "Low" is a scope, not an exemption.
- **Change control theater.** Emergency changes to protection systems happen; CIP-010 requires they still be documented, tested, and baselined afterward. The emergency is not the exemption — the follow-through is the requirement.

## References

- NERC CIP Standards (CIP-002 through CIP-014) — https://www.nerc.com/pa/Stand/Pages/default.aspx
- NERC Reliability Standard Audit Worksheets (RSAWs) — via NERC compliance resources
- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- E-ISAC (Electricity Information Sharing and Analysis Center) — https://www.eisac.com/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
