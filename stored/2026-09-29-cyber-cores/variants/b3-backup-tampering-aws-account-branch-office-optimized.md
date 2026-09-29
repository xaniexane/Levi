---
skill_id: cyber_b3_backup_tampering_aws_account_branch_office_optimized
name: Backup Tampering Defense for AWS Accounts in Branch Offices (Optimized Maturity)
description: "Backup Tampering defense playbook for AWS Accounts in Branch Offices at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, cloud, aws, branch, network, maturity-optimized]
version: 1.0.0
---
# Backup Tampering Defense for AWS Accounts in Branch Offices (Optimized Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to AWS Accounts in Branch Offices at Optimized maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for AWS Accounts; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
