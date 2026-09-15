---
skill_id: cyber_detecting_dcsync_attack_in_active_directory
name: Detecting DCSync Attack in Active Directory
description: Detect DCSync credential replication abuse with 4662 monitoring, replication auditing, and privileged-account baselines.
risk: info
permissions: []
requires_confirmation: false
tags: [active-directory, detection, credentials]
version: 1.0.0
---
## Purpose

Detect DCSync — attackers abusing domain replication to pull password hashes for any account without touching the DC's disk. It's stealthy, powerful, and fully detectable if you're watching the right event. This is one of the highest-value AD detections you can build.

## When to use

- Building Active Directory threat detection (DCSync is a must-have detection).
- Hunting after a suspected domain compromise.
- Investigating how an attacker obtained privileged credentials.
- Validating that replication monitoring is actually working.

## Prerequisites

- Security event logging from all domain controllers centralized (Event ID 4662 specifically).
- An inventory of legitimate replication sources: every DC's computer account.
- Baseline of accounts with replication rights (Enterprise Admins, Domain Admins, and any delegated).
- Alerting path with AD incident response runbooks.

## Procedure

1. **Enable the right auditing.** Ensure "Directory Service Access" auditing captures Event ID 4662 on all DCs with the replication GUIDs (`1131f6aa-9c07-11d1-f79f-00c04fc2dcd2` and friends). Without this, DCSync is invisible — verify with a test that 4662 events are actually arriving in the SIEM from every DC.
2. **Alert on replication from non-DCs.** The core detection: 4662 replication-access events where the subject is NOT a domain controller computer account. Legitimate replication only comes from DCs — any user account, member server, or workstation performing DRSUAPI replication calls is an attacker (or a misconfigured tool; investigate either way).
3. **Baseline and monitor replication privileges.** Audit which accounts hold `Replicating Directory Changes` and `Replicating Directory Changes All` rights. Alert on any grant of these rights — they're the DCSync prerequisite, and legitimate grants are rare and change-controlled. Attackers sometimes grant themselves these rights first; catch the grant, not just the sync.
4. **Detect the DCSync-adjacent techniques.** Monitor for: DCShadow (rogue DC registration — new SPNs, fake DC computer accounts, then replication), secretsdump-style patterns (DCSync followed by mass 4768/4769 anomalies as stolen hashes get used), and AdminSDHolder or ACL modifications granting replication rights indirectly.
5. **Correlate with credential-use anomalies.** After a DCSync alert, hunt for: the targeted accounts authenticating from new hosts, golden-ticket indicators (TGTs with anomalous lifetimes), and lateral movement from the attacker's host. DCSync is usually followed by privilege escalation using the stolen hashes — the detection starts the timeline, not ends it.
6. **Scope the compromise.** Determine: which accounts' hashes were replicated (check the 4662 object names and subsequent access), the full activity window, and whether the attacker's account still holds replication rights. Assume every replicated credential is compromised — that's the reset scope.
7. **Respond and harden.** Remove replication rights from the compromised account, force password resets for all targeted accounts (KRBTGT twice if domain compromise is confirmed), audit replication rights quarterly, and consider Protected Users group / authentication policies for the most sensitive accounts to limit hash exposure.

## Expected outputs

- 4662-based DCSync detection alerting on replication from non-DC accounts, verified on all DCs.
- Replication-rights inventory with change alerting; DCShadow detection.
- Credential-reset scoping procedures tied to replicated-account identification.

## Pitfalls

- 4662 not collected or filtered out — the detection silently doesn't exist; verify event flow.
- Allowlisting "known tools" broadly — some legitimate tools replicate; scope exceptions to specific accounts, not categories.
- Missing the rights-grant precursor — the attacker grants themselves replication rights days before syncing.
- Single KRBTGT reset — golden tickets from DCSync'd KRBTGT survive one reset.
- Treating DCSync as the whole incident — it's the credential theft; find the initial access and the subsequent use.

## References

- Microsoft Learn — Active Directory replication, Event ID 4662, DRSUAPI auditing
- MITRE ATT&CK T1003.006 (OS Credential Dumping: DCSync)
- NIST SP 800-53 AC-2 / AC-6 (account management, least privilege)
- SANS / DFIR community guidance on DCSync detection queries
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
