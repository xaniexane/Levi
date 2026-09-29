---
skill_id: cyber_b3_wmi_persistence_file_server_aws_cloud_developing
name: WMI Persistence Defense for File Servers in AWS Cloud (Developing Maturity)
description: "WMI Persistence defense playbook for File Servers in AWS Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, data, linux, cloud, aws, maturity-developing]
version: 1.0.0
---
# WMI Persistence Defense for File Servers in AWS Cloud (Developing Maturity)

## Purpose

WMI event subscriptions trigger payloads on system events (timers, logons) with no visible scheduled task or service. They are fileless, stealthy, and missed by autorun tools that do not enumerate the WMI repository. Applies to File Servers in AWS Cloud at Developing maturity.

## When to use

- New __EventFilter/__EventConsumer/__FilterToConsumerBinding instances in the WMI repository, especially ActiveScript or CommandLine consumers with encoded commands.
- WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI operational log entries for subscription creation.
- Persistence that survives task/service cleanup — the classic sign the mechanism is WMI-based.
- Lens: Best telemetry: object-access auditing (who opened/modified what) + share-permission reviews. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in File-access audit events (4663/4656 on Windows; auditd on Linux) for sensitive shares and Share and NTFS/ACL permission exports; recent permission-change events; run `Get-SmbShare | Select-Object Name, Path, Description; echo ---; Get-SmbShareAccess -Name <share>` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 100 | Group-Object {$_.Properties[1].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** Enumerate all event subscriptions (Get-WMIObject -Namespace root\subscription) and inspect each consumer's command line. Then: Correlate subscription creation time with the initial compromise to confirm it is attacker-planted, not admin tooling.
4. **Contain and harden.** Alert on WMI subscription creation events; restrict WMI namespace permissions to administrators. Asset layer: Access-based enumeration, least-privilege share/NTFS rights, no Everyone:Full Control anywhere. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring a host clean after checking tasks/services/registry but never looking at WMI subscriptions.
- Removing the consumer but leaving the filter and binding, which error silently and get recreated by the implant.

## References

- MITRE ATT&CK: T1047 (Execution: Windows Management Instrumentation)
- Vendor logging and hardening baselines for File Servers; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
