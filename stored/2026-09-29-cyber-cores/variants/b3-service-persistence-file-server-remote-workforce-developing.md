---
skill_id: cyber_b3_service_persistence_file_server_remote_workforce_developing
name: Malicious Service Persistence Defense for File Servers in Remote Workforce (Developing Maturity)
description: "Malicious Service Persistence defense playbook for File Servers in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, data, linux, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# Malicious Service Persistence Defense for File Servers in Remote Workforce (Developing Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to File Servers in Remote Workforce at Developing maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in File-access audit events (4663/4656 on Windows; auditd on Linux) for sensitive shares and Share and NTFS/ACL permission exports; recent permission-change events; run `Get-SmbShare | Select-Object Name, Path, Description; echo ---; Get-SmbShareAccess -Name <share>` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 100 | Group-Object {$_.Properties[1].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for File Servers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
