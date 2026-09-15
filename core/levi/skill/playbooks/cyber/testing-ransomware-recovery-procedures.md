---
skill_id: cyber_testing_ransomware_recovery_procedures
name: Testing Ransomware Recovery Procedures
description: Validate ransomware recovery readiness with tabletop exercises, restore drills, and immutable backup tests.
risk: low
permissions: []
requires_confirmation: false
tags: [incident-response, ransomware, resilience]
version: 1.0.0
---
## Purpose
Recovery procedures that have never been tested fail when needed. This playbook validates ransomware readiness without a real incident: tabletop exercises for decision-making, technical restore drills for backups, and verification that immutable/offline copies actually exist and work within RTO/RPO targets.

## When to use
- Annual resilience validation or after backup architecture changes.
- Pre-audit evidence collection for recovery capabilities.
- After leadership or IR team turnover.
- Following a near-miss or industry ransomware event.

## Prerequisites
- Documented ransomware recovery procedures and defined RTO/RPO per tier.
- Backup inventory: what is backed up, where, retention, and immutability status.
- Isolated restore test environment that cannot impact production.
- Exercise facilitator and participants from IT, security, legal, and communications.

## Procedure
1. Run a tabletop exercise: present a realistic ransomware scenario and walk decisions (isolation, evidence, comms, ransom stance).
2. Test backup integrity: verify immutability locks, offline copies, and that backup credentials are separated from domain admin.
3. Perform a restore drill of tier-1 systems into the isolated environment; measure actual RTO against targets.
4. Verify restored data integrity with checksums and application-level smoke tests.
5. Test credential reset procedures: can you rebuild identity (AD/Entra) from a known-clean state?
6. Validate communications: executive briefing templates, customer notification drafts, and law-enforcement contacts.
7. Document gaps found (missing backups, untested restores, unclear decisions) with owners and deadlines.
8. Re-run drills after remediation; track RTO/RPO achievement trends.
9. Include third-party and SaaS data in restore drills; backups often stop at the data center edge.
10. Involve the actual on-call rotation in drills, not just the IR team.
11. Test the communications plan with a simulated press inquiry during the exercise.

## Expected outputs
- Tabletop exercise report with decisions and gaps.
- Restore drill results: measured RTO/RPO vs targets.
- Remediation backlog with owners and retest dates.
- SaaS and third-party restore coverage assessment.
- On-call participation records for drills.
- Communications-plan exercise results.

## Pitfalls
- Testing restores of one server does not validate full-environment rebuild; scope drills realistically.
- Backups administered with domain credentials are compromised with the domain; separate them.
- RTO measured without application validation overstates readiness.
- Tabletop without executives produces plans nobody with authority has agreed to.
- Drills that never involve the actual on-call rotation test the wrong team.
- SaaS data without backup coverage is discovered too late; inventory it now.
- Tabletop-only programs miss the technical failures; alternate with hands-on drills.
- Recovery runbooks stored only on the network are unavailable during the incident; keep offline copies.

## References
- CISA StopRansomware Guide (cisa.gov/stopransomware).
- NIST SP 800-61 Rev. 2 and SP 800-34 (contingency planning).
- NIST Cybersecurity Framework: Recover function.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
