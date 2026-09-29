---
skill_id: cyber_b3_registry_persistence_aws_account_on_prem_datacenter_developing
name: Registry Persistence Defense for AWS Accounts in On-Premises Datacenter (Developing Maturity)
description: "Registry Persistence defense playbook for AWS Accounts in On-Premises Datacenter at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, cloud, aws, on-prem, datacenter, maturity-developing]
version: 1.0.0
---
# Registry Persistence Defense for AWS Accounts in On-Premises Datacenter (Developing Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to AWS Accounts in On-Premises Datacenter at Developing maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for AWS Accounts; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
