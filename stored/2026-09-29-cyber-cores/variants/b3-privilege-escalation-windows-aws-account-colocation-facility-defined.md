---
skill_id: cyber_b3_privilege_escalation_windows_aws_account_colocation_facility_defined
name: Windows Privilege Escalation Defense for AWS Accounts in Colocation Facilities (Defined Maturity)
description: "Windows Privilege Escalation defense playbook for AWS Accounts in Colocation Facilities at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, cloud, aws, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# Windows Privilege Escalation Defense for AWS Accounts in Colocation Facilities (Defined Maturity)

## Purpose

From standard user to SYSTEM/Administrator via unquoted service paths, writable service binaries, AlwaysInstallElevated, token manipulation, or kernel exploits. Windows privesc is usually a misconfiguration the attacker read, not a zero-day they brought. Applies to AWS Accounts in Colocation Facilities at Defined maturity.

## When to use

- Service creation or modification events (7045/4697) pointing at user-writable paths, or processes spawning as SYSTEM from unexpected parents.
- Registry writes to AlwaysInstallElevated keys, accessibility binary replacement (sethc/utilman), or token duplication API patterns in EDR telemetry.
- Enumeration tooling: whoami /priv, accesschk, or PowerShell privesc scripts running before the escalation.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Pin down the primitive: unquoted path, weak service ACL, scheduled task with stored creds, or kernel CVE — then check how many fleet hosts share it. Then: Review what the elevated access touched: SAM/LSASS access after escalation means credential theft followed.
4. **Contain and harden.** Fix service ACLs and paths fleet-wide, disable AlwaysInstallElevated, and enforce signed-driver and LSA protection policies. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reimaging one host while the GPO-deployed misconfiguration recreates the hole on every rebuild.
- Missing that the attacker already dumped credentials post-escalation — scope the follow-on theft, not just the privesc.

## References

- MITRE ATT&CK: T1068 (Privilege Escalation: Exploitation for Privilege Escalation)
- Vendor logging and hardening baselines for AWS Accounts; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
