---
skill_id: cyber_b3_insider_data_theft_code_repository_aws_cloud_foundational
name: Insider Data Theft Defense for Code Repositories in AWS Cloud (Foundational Maturity)
description: "Insider Data Theft defense playbook for Code Repositories in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, devops, supply-chain, secrets, cloud, aws, maturity-foundational]
version: 1.0.0
---
# Insider Data Theft Defense for Code Repositories in AWS Cloud (Foundational Maturity)

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. Applies to Code Repositories in AWS Cloud at Foundational maturity.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context
- Vendor logging and hardening baselines for Code Repositories; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
