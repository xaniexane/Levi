---
skill_id: cyber_b3_ransomware_encryption_windows_server_colocation_facility_developing
name: Ransomware Encryption Defense for Windows Servers in Colocation Facilities (Developing Maturity)
description: "Ransomware Encryption defense playbook for Windows Servers in Colocation Facilities at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [malware, ransomware, windows, server, on-prem, colocation, maturity-developing]
version: 1.0.0
---
# Ransomware Encryption Defense for Windows Servers in Colocation Facilities (Developing Maturity)

## Purpose

Ransomware encrypts files and demands payment, usually after days of dwell time spent disabling recovery. Speed of isolation decides whether you lose one host or the fleet. Never pay without a deliberate, documented decision process. Applies to Windows Servers in Colocation Facilities at Developing maturity.

## When to use

- EDR fires on mass file rename/extension changes, vssadmin delete shadows, bcdedit recovery disabling, or known ransomware process names within seconds of each other.
- Ransom notes (README, DECRYPT files) appearing in multiple directories, wallpaper changes, or a sudden burst of encrypted file extensions across shares.
- Precursor activity in the prior 72 hours: disabled EDR tamper protection, cleared event logs, or backup job failures and backup-server logons from unusual accounts.
- Lens: Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log (7045 service installs, 4720 account creation, 4732 group changes) and IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\Windows\System32\Tasks; run `Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message` then `Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter "Name='$($_.Name)'" | Select-Object Name, PathName, StartName }`.
3. **Analyze.** Identify the variant from the note text, extension, and ransom portal; check public decryptor availability before any recovery decision — some variants have free decryptors. Then: Reconstruct the entry vector (phishing, exposed RDP/VPN, software vulnerability) and the dwell timeline: first access, privilege escalation, backup targeting, detonation.
4. **Contain and harden.** Immutable, offline-tested backups with alerting on backup tampering; network segmentation so one host cannot reach all shares. Asset layer: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rebuilding from backups that the attacker already found and poisoned — verify backup integrity and isolation first.
- Paying the ransom without confirming the decryptor works and without legal/regulatory review of sanctions exposure.

## References

- MITRE ATT&CK: T1486 (Impact: Data Encrypted for Impact)
- Vendor logging and hardening baselines for Windows Servers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
