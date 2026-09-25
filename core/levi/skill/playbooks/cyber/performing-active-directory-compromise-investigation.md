---
skill_id: cyber_performing_active_directory_compromise_investigation
name: Performing Active Directory Compromise Investigation
description: Investigate a suspected Active Directory compromise from detection through recovery.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, incident-response, forensics]
version: 1.0.0
---

## Purpose
This playbook investigates suspected AD compromise: determining whether the directory is breached, scoping attacker control (persistence, golden tickets, DCSync), and driving a safe recovery that does not leave the attacker in place.

## When to use
- Alerts suggest DCSync, golden/silver ticket use, or DC compromise.
- An intrusion investigation traces back to domain-level access.
- Post-ransomware: AD is almost always in scope and must be validated.

## Prerequisites
- Declared incident with authority to collect from domain controllers.
- Forensic images or at minimum ntds.dit/registry hives from DCs, plus DC security event logs.
- Offline, known-clean recovery media and credential-reset capability planned in advance.

## Procedure
1. **Triage the signal.** Validate the alert: anomalous replication (DCSync), impossible Kerberos ticket lifetimes, or unexpected privileged logons — rule out admin tooling first.
2. **Preserve DC evidence.** Image domain controllers before any remediation; capture ntds.dit, SYSTEM/SECURITY hives, and event logs with chain of custody.
3. **Hunt for persistence.** Check for: skeleton keys, DCShadow artifacts, malicious GPOs, SID-history injection, AdminSDHolder tampering, and shadow credentials on privileged accounts.
4. **Scope credential exposure.** Identify which accounts the attacker controlled and for how long; assume krbtgt compromise if evidence supports it, and plan the double-reset.
5. **Analyze the timeline.** Correlate DC logs with endpoint and network telemetry to reconstruct initial access, privilege escalation, and persistence installation.
6. **Execute controlled recovery.** Follow a sequenced plan: isolate, rebuild or restore DCs from known-clean media, reset krbtgt twice, reset all privileged (then all) credentials, and remove identified persistence — in the right order.
7. **Validate and monitor.** Post-recovery, hunt for re-persistence, monitor for the attacker's known TTPs, and conduct a lessons-learned review focused on the AD attack path.

8. **Assume cloud trust impact.** If AD syncs to Entra ID or federates to cloud apps, scope the compromise into those trust relationships; attackers follow the sync.
9. **Document for regulators and insurers.** Preserve the evidence and timeline in a form suitable for breach notification and cyber-insurance claims from the start.

## Expected outputs
- Compromise determination with evidence: what the attacker controlled and for how long.
- Recovery plan executed in sequence with verification checkpoints.
- Hardening backlog addressing the exploited AD weaknesses.
- Example: investigation confirms DCSync from an external IP against two DCs over 6 days; recovery follows the sequenced plan — rebuilt DCs, double krbtgt reset, full credential rotation — with each step verified before the next.

## Pitfalls
- Resetting passwords before removing persistence: the attacker just re-takes them.
- Single krbtgt reset: do it twice with replication time between, or old tickets survive.
- Rebuilding DCs from backups that predate the compromise window without verifying cleanliness.

- Recovering DCs from system-state backups without verifying the backup predates the compromise; you can restore the attacker along with the directory.
- Skipping the lessons-learned because everyone is exhausted; the same AD weaknesses will be exploited again within a year.

## References
- Microsoft Learn: detecting and recovering from AD compromise (learn.microsoft.com).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- CISA AD security guidance (cisa.gov) — hardening after compromise.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
