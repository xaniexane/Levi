---
skill_id: cyber_b3_privilege_escalation_sudo_windows_server_colocation_facility_defined
name: Linux Privilege Escalation Defense for Windows Servers in Colocation Facilities (Defined Maturity)
description: "Linux Privilege Escalation defense playbook for Windows Servers in Colocation Facilities at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privilege-escalation, windows, server, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# Linux Privilege Escalation Defense for Windows Servers in Colocation Facilities (Defined Maturity)

## Purpose

Attackers turn a low-privilege Linux foothold into root via sudo misconfigurations, SUID binaries, kernel exploits, or writable service files. Harden the escalation paths and you contain most Linux intrusions at the beachhead. Applies to Windows Servers in Colocation Facilities at Defined maturity.

## When to use

- Sudo invocations of unusual binaries, sudoers file reads by non-admins, or successful sudo from accounts that never used it before.
- Execution of known privesc enumeration scripts (LinPEAS-style), SUID binary abuse, or kernel exploit artifacts in logs.
- New entries in sudoers.d, unexpected SUID bits, or service files modified by non-root users.
- Lens: Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log (7045 service installs, 4720 account creation, 4732 group changes) and IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\Windows\System32\Tasks; run `Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message` then `Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter "Name='$($_.Name)'" | Select-Object Name, PathName, StartName }`.
3. **Analyze.** Identify the exact escalation primitive: which misconfiguration or vulnerability was used, and whether it is systemic across the fleet or host-specific. Then: Check for persistence installed with the new privileges: new SSH keys in root's authorized_keys, cron jobs, or systemd units.
4. **Contain and harden.** Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID from unnecessary binaries, and keep kernels patched. Asset layer: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the host without fixing the fleet-wide sudoers misconfiguration that enabled it.
- Assuming container escape is out of scope — check whether the foothold was a container with host mounts.

## References

- MITRE ATT&CK: T1548.003 (Privilege Escalation: Sudo and Sudo Caching)
- Vendor logging and hardening baselines for Windows Servers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
