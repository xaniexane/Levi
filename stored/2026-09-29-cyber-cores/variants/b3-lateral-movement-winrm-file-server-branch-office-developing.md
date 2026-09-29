---
skill_id: cyber_b3_lateral_movement_winrm_file_server_branch_office_developing
name: WinRM Lateral Movement Defense for File Servers in Branch Offices (Developing Maturity)
description: "WinRM Lateral Movement defense playbook for File Servers in Branch Offices at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, data, linux, branch, network, maturity-developing]
version: 1.0.0
---
# WinRM Lateral Movement Defense for File Servers in Branch Offices (Developing Maturity)

## Purpose

Windows Remote Management gives attackers remote PowerShell on any host where WinRM is enabled — quieter than PsExec, built into the OS, and often left on by default in enterprises. Applies to File Servers in Branch Offices at Developing maturity.

## When to use

- WinRM operational log (Microsoft-Windows-WinRM/Operational) showing connections from non-admin workstations, or wsmprovhost spawning powershell with encoded commands.
- Event 4624 type-3 logons to the WinRM port (5985/5986) from hosts outside the management subnet.
- PowerShell remoting sessions (event 400/800) executing reconnaissance or credential-access commands.
- Lens: Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in File-access audit events (4663/4656 on Windows; auditd on Linux) for sensitive shares and Share and NTFS/ACL permission exports; recent permission-change events; run `Get-SmbShare | Select-Object Name, Path, Description; echo ---; Get-SmbShareAccess -Name <share>` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 100 | Group-Object {$_.Properties[1].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Extract the remote commands from PowerShell operational logs (4104) on the target to see exactly what the attacker ran. Then: Inventory which hosts have WinRM enabled and reachable — the attack surface is every one of them.
4. **Contain and harden.** Restrict WinRM to management hosts via host firewall and GPO; disable where not needed. Asset layer: Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Forgetting WinRM over HTTPS (5986) when firewalling only 5985.
- PowerShell logging gaps: without module/script-block logging, remote commands are invisible — enable both.

## References

- MITRE ATT&CK: T1021.006 (Lateral Movement: Windows Remote Management)
- Vendor logging and hardening baselines for File Servers; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
