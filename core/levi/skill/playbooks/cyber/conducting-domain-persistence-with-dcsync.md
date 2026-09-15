---
skill_id: cyber_conducting_domain_persistence_with_dcsync
name: Detecting and Preventing DCSync Attacks
description: Defensive playbook for detecting DCSync-style credential replication abuse and hardening Active Directory against it.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, detection, hardening]
version: 1.0.0
---
## Purpose
DCSync abuses legitimate domain-replication privileges to pull password hashes from a domain controller without running code on it, giving attackers persistent credential access. This playbook is defensive: how to detect replication-abuse in logs, audit who holds replication rights, and remove the conditions that make DCSync possible. No offensive usage is described.

## When to use
- Hunting for credential-theft activity in an Active Directory environment.
- Auditing which accounts hold replication privileges (a common persistence path).
- Responding to alerts about unusual directory replication traffic.
- Validating AD hardening after a compromise or assessment.

## Prerequisites
- Directory Service event logging on domain controllers (notably event 4662 with replication GUIDs).
- Inventory of accounts with Replicating Directory Changes rights.
- SIEM capable of correlating 4662 events with source hosts and accounts.
- Change process for modifying ACLs on the domain naming context.

## Procedure
1. Baseline legitimate replication. Identify which domain controllers replicate with each other normally, so abnormal sources stand out.
2. Audit replication privileges. Enumerate accounts with Replicating Directory Changes, All, and Filtered Set rights; every non-DC account is suspect until justified.
3. Build the detection. Alert on 4662 events for replication GUIDs originating from non-domain-controller hosts or unexpected accounts.
4. Hunt historically. Search for past replication events from unusual sources; DCSync leaves a log trail when auditing is enabled.
5. Remove unjustified rights. Strip replication privileges from accounts that do not need them; require change tickets for any future grants.
6. Protect privileged accounts. Ensure accounts with replication rights are in the Protected Users group or tiered appropriately, with MFA where applicable.
7. Respond to findings. If unauthorized DCSync is confirmed, treat it as credential compromise: reset the KRBTGT account twice and rotate credentials for affected accounts.
8. Maintain the control. Re-audit replication rights quarterly and after every AD privilege change; keep the detection tuned.

## Expected outputs
- Detection rule for unauthorized directory replication.
- Audited list of replication-privileged accounts with justifications.
- Incident response actions if abuse is confirmed.

## Pitfalls
- Without 4662 auditing enabled, DCSync is invisible; enable it before you need it.
- Legitimate tools (some backup and sync products) use replication rights; baseline first.
- Resetting KRBTGT is disruptive if done wrong; follow the double-reset procedure carefully.
- Focusing only on DCSync while ignoring other replication-right abuses.

## References
- Microsoft Learn: Active Directory audit policy and event 4662
- MITRE ATT&CK: T1003.006 (DCSync)
- CISA guidance on Active Directory hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
