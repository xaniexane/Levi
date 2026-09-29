---
skill_id: cyber_b3_backup_tampering_windows_workstation_colocation_facility_optimized
name: Backup Tampering Defense for Windows Workstations in Colocation Facilities (Optimized Maturity)
description: "Backup Tampering defense playbook for Windows Workstations in Colocation Facilities at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, windows, endpoint, on-prem, colocation, maturity-optimized]
version: 1.0.0
---
# Backup Tampering Defense for Windows Workstations in Colocation Facilities (Optimized Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Windows Workstations in Colocation Facilities at Optimized maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security event log (4624/4625 logons, 4688 process creation, 7045 service installs) and Sysmon operational log and PowerShell operational log (4104 script blocks); run `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}` then `autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v "Microsoft Corporation"`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Windows Workstations; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
