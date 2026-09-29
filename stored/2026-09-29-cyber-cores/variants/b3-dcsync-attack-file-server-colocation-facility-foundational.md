---
skill_id: cyber_b3_dcsync_attack_file_server_colocation_facility_foundational
name: DCSync Attack Defense for File Servers in Colocation Facilities (Foundational Maturity)
description: "DCSync Attack defense playbook for File Servers in Colocation Facilities at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, data, windows, linux, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# DCSync Attack Defense for File Servers in Colocation Facilities (Foundational Maturity)

## Purpose

With replication rights, an attacker impersonates a domain controller and pulls password hashes for ANY account — including krbtgt — via normal replication traffic. It looks like DC-to-DC chatter, which is why it evades naive monitoring. Applies to File Servers in Colocation Facilities at Foundational maturity.

## When to use

- 4662 (directory object access) on the domain root or krbtgt account by a principal that is not a real domain controller.
- Replication traffic (DRS) originating from a non-DC host, or a DC requesting replication far outside the normal schedule.
- Newly granted DS-Replication-Get-Changes rights (especially Get-Changes-All) to users, groups, or computers.
- Lens: Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in File-access audit events (4663/4656 on Windows; auditd on Linux) for sensitive shares and Share and NTFS/ACL permission exports; recent permission-change events; run `Get-SmbShare | Select-Object Name, Path, Description; echo ---; Get-SmbShareAccess -Name <share>` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 100 | Group-Object {$_.Properties[1].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Identify which account performed the sync and which hashes were pulled — a krbtgt pull means the entire domain's Kerberos trust must be reset (double krbtgt rotation). Then: Review how the attacker gained replication rights: compromised admin, delegated rights sprawl, or ACL abuse.
4. **Contain and harden.** Audit and strip replication rights to the minimum; alert on any grant of Get-Changes-All. Asset layer: Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting user passwords but not the krbtgt — golden tickets forged from a stolen krbtgt survive password resets.
- Missing that DCSync needs only replication rights, not Domain Admin — delegated-rights sprawl is the usual enabler.

## References

- MITRE ATT&CK: T1003.006 (Credential Access: DCSync)
- Vendor logging and hardening baselines for File Servers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
