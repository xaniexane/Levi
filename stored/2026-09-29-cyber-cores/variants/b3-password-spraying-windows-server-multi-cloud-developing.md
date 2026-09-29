---
skill_id: cyber_b3_password_spraying_windows_server_multi_cloud_developing
name: Password Spraying Defense for Windows Servers in Multi-Cloud (Developing Maturity)
description: "Password Spraying defense playbook for Windows Servers in Multi-Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, windows, server, cloud, multi-cloud, maturity-developing]
version: 1.0.0
---
# Password Spraying Defense for Windows Servers in Multi-Cloud (Developing Maturity)

## Purpose

Attackers try a small set of common passwords against many usernames, staying under per-account lockout thresholds. It is quieter than stuffing and specifically tuned to evade lockout policies, often running for days or weeks. Applies to Windows Servers in Multi-Cloud at Developing maturity.

## When to use

- A handful of failed logons per account (1-3) spread across hundreds of accounts from one or a few IPs, repeating on a schedule — the classic low-and-slow pattern.
- The same few passwords attempted everywhere (SeasonYear!, Company123, Password1); check by aggregating failed-logon password hashes where your IdP logs them.
- Spray bursts correlated with newly published password lists or timed to holidays/weekends when response is slower.
- Lens: Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log (7045 service installs, 4720 account creation, 4732 group changes) and IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\Windows\System32\Tasks; run `Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message` then `Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter "Name='$($_.Name)'" | Select-Object Name, PathName, StartName }`.
3. **Analyze.** Reconstruct the spray window: first-seen to last-seen per source IP, and list every account with even one success inside the window — those are confirmed or suspected takeovers. Then: Check whether sprayed accounts share traits (same OU, same onboarding batch, service accounts) to find how the username list was built.
4. **Contain and harden.** Smart lockout (soft lockout with increasing delays) plus alerting on distributed low-volume failures, not just lockouts. Asset layer: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Per-account lockout thresholds alone will not catch spraying; you need cross-account velocity detection.
- Treating one success as an isolated incident misses the campaign — always scope the full spray window.

## References

- MITRE ATT&CK: T1110.003 (Credential Access: Brute Force: Password Spraying)
- Vendor logging and hardening baselines for Windows Servers; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
