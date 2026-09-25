---
skill_id: cyber_detecting_privilege_escalation_attempts
name: Detecting Privilege Escalation Attempts
description: Detect local and domain privilege-escalation attempts across endpoints.
risk: low
permissions: []
requires_confirmation: false
tags: [privilege-escalation, detection, endpoint]
version: 1.0.0
---
## Purpose

Privilege escalation — from user to admin, admin to SYSTEM, or user to domain admin — is the pivot point of most intrusions. This playbook gives defenders a cross-platform detection approach: the Windows and Linux signals that reveal escalation attempts, how to separate attacker techniques from legitimate admin work, and the response escalation path.

## When to use

- You need privilege-escalation detection coverage across the fleet.
- EDR shows suspicious admin-tool usage and you need a triage framework.
- Threat hunting after initial access: is the attacker now privileged?
- Compliance requires monitoring of privileged-access events.

## Prerequisites

- Endpoint telemetry: Windows Security logs (4672 special privileges, 4624 Type 2, 4688 process creation) and Sysmon; Linux auditd/auth logs (sudo, su, polkit, SUID execution).
- Inventory of who legitimately holds admin rights and which tools they use.
- Baseline of normal elevation patterns: helpdesk workflows, deployment tools, patching.
- UAC/sudo configuration knowledge per environment.

## Procedure

1. Cover the Windows escalation signals. Alert on: 4672 (special privileges assigned) for non-admin accounts or unusual hosts; processes running as SYSTEM spawned by user applications; UAC bypass indicators (fodhelper, eventvwr, sdclt abuse patterns); token manipulation (process token theft); and new local admin account creation or group additions (4728/4732/4756). Weight heavily when the parent chain starts from Office apps, browsers, or LOLBins.
2. Cover the Linux escalation signals. Alert on: sudo/su failures followed by success (brute-forcing then succeeding), SUID binary execution anomalies (especially custom or recently modified SUID files), polkit exploitation patterns, kernel-exploit indicators (unexpected crashes followed by root shells), cron/systemd persistence with privilege changes, and /etc/passwd or /etc/sudoers modifications.
3. Separate legitimate elevation from attacks with context. Legitimate: known admin accounts, from admin workstations, during change windows, using documented tools. Suspicious: standard users elevating, elevation from user workstations to servers, off-hours elevation outside change windows, and elevation chains (user → local admin → SYSTEM → domain). Build rules that encode this context rather than alerting on 'admin activity'.
4. Hunt the precursors. Escalation rarely comes first: look back from the escalation event for initial access (phishing, exploitation), discovery commands, and credential-access attempts. An escalation alert with no precursor is either a false positive or a sign your initial-access logging has gaps — investigate both.
5. Respond by scope of achieved privilege. Local admin on one host: isolate, investigate, reimage if compromised. SYSTEM/root: assume full host compromise, capture forensics, reset credentials used on the host. Domain admin: full incident response — forest-wide credential reset planning, persistence hunting across DCs, and KRBTGT assessment. Match the response to the privilege achieved.
6. Shrink the escalation surface: remove local admin rights where possible, enforce UAC/sudo properly, patch privilege-escalation CVEs promptly (they're among the most exploited), audit SUID binaries and scheduled tasks regularly, and move to just-in-time privileged access.

## Expected outputs

- Cross-platform escalation detection rules: Windows (4672, UAC bypass, token theft, group changes) and Linux (sudo/su, SUID, polkit, persistence).
- Legitimate-elevation baseline: accounts, hosts, tools, change windows.
- Response matrix keyed to achieved privilege level.
- Hardening backlog: local-admin reduction, JIT access, patch status of privesc CVEs.

## Pitfalls

- Alerting on all admin activity without context buries analysts — encode the legitimate patterns.
- UAC bypass and token-manipulation techniques evolve; behavior rules (parent/child, integrity level changes) outlast technique-specific ones.
- Linux environments without auditd miss most escalation signals — ensure syscall auditing is deployed.
- Treating local-admin escalation as 'just a workstation issue' misses the credential-theft that follows.
- Patching privesc CVEs late is the most common root cause — detection doesn't replace patching.

## References

- MITRE ATT&CK TA0004 (Privilege Escalation) — https://attack.mitre.org/tactics/TA0004/; MITRE ATT&CK T1548 (Abuse Elevation Control Mechanism); NIST SP 800-53 AC-6 (Least Privilege)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
