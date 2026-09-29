---
skill_id: cyber_b3_data_exfiltration_windows_workstation_branch_office_managed
name: Data Exfiltration Defense for Windows Workstations in Branch Offices (Managed Maturity)
description: "Data Exfiltration defense playbook for Windows Workstations in Branch Offices at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [exfiltration, dlp, windows, endpoint, branch, network, maturity-managed]
version: 1.0.0
---
# Data Exfiltration Defense for Windows Workstations in Branch Offices (Managed Maturity)

## Purpose

Sensitive data leaving the network — the moment an intrusion becomes a breach. Quantifying WHAT left is more important than blocking the channel after the fact; notification obligations depend on the data, not the technique. Applies to Windows Workstations in Branch Offices at Managed maturity.

## When to use

- Egress spikes: large uploads to external hosts, cloud storage, or paste sites from servers that normally receive more than they send.
- Staging activity: large archives (zip/7z/rar) created in temp directories, database dumps, or mailbox exports shortly before the transfer.
- DLP alerts on regulated data patterns (SSN, card numbers, PHI formats) in outbound traffic, or DNS/ICMP exfil at low volume.
- Lens: Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security event log (4624/4625 logons, 4688 process creation, 7045 service installs) and Sysmon operational log and PowerShell operational log (4104 script blocks); run `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}` then `autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v "Microsoft Corporation"`.
3. **Analyze.** Reconstruct the exfil set: source paths, file types, record counts, and data classification — involve legal early for notification scoping. Then: Preserve full packet/proxy logs of the transfer; they prove what left and are evidence for regulators and law enforcement.
4. **Contain and harden.** DLP policies with blocking on bulk sensitive-data egress, plus alerting on archive creation and database dump commands. Asset layer: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the transfer but never determining what was in it — you cannot scope a breach on 'we blocked something'.
- Forgetting cloud audit logs: exfil via sanctioned SaaS (personal Drive, Dropbox) bypasses network DLP.

## References

- MITRE ATT&CK: T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for Windows Workstations; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
