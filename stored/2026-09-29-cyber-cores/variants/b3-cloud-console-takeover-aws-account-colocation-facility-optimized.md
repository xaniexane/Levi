---
skill_id: cyber_b3_cloud_console_takeover_aws_account_colocation_facility_optimized
name: Cloud Console Takeover Defense for AWS Accounts in Colocation Facilities (Optimized Maturity)
description: "Cloud Console Takeover defense playbook for AWS Accounts in Colocation Facilities at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, identity, aws, on-prem, colocation, maturity-optimized]
version: 1.0.0
---
# Cloud Console Takeover Defense for AWS Accounts in Colocation Facilities (Optimized Maturity)

## Purpose

Stolen cloud credentials used in the web console give attackers point-and-click infrastructure control. Console logons from unusual locations followed by IAM changes are the classic takeover sequence. Applies to AWS Accounts in Colocation Facilities at Optimized maturity.

## When to use

- CloudTrail/Entra sign-in logs showing console logons from new countries or anonymizing services for privileged users.
- IAM policy changes, new access keys, or new users created within minutes of the anomalous logon.
- Disabling of CloudTrail/logging or deletion of log data — the attacker covering tracks.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Reconstruct the full API call sequence after takeover: what was created, modified, exfiltrated, or destroyed. Then: Check for persistence: new IAM users, roles with trust policies pointing outward, or modified instance user-data.
4. **Contain and harden.** Phishing-resistant MFA on all console users, especially root/ break-glass; SCPs preventing logging disablement. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the compromised user's keys but missing the backdoor IAM role the attacker created.
- Trusting the account's own logs after the attacker had admin — verify against the immutable archive.

## References

- MITRE ATT&CK: T1078 (Persistence: Valid Accounts) — cloud console
- Vendor logging and hardening baselines for AWS Accounts; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
