---
skill_id: cyber_b3_credential_stuffing_aws_account_multi_cloud_optimized
name: Credential Stuffing Defense for AWS Accounts in Multi-Cloud (Optimized Maturity)
description: "Credential Stuffing defense playbook for AWS Accounts in Multi-Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, cloud, aws, multi-cloud, maturity-optimized]
version: 1.0.0
---
# Credential Stuffing Defense for AWS Accounts in Multi-Cloud (Optimized Maturity)

## Purpose

Attackers replay username/password pairs stolen from third-party breaches against your login endpoints, betting on password reuse. It shows up as high-volume failed logons from distributed IPs, occasionally followed by a small number of successful takeovers. Applies to AWS Accounts in Multi-Cloud at Optimized maturity.

## When to use

- Authentication logs show a spike in failed logons (often 100s per minute) from many source IPs against a single login endpoint, with a low success rate and common password patterns.
- Successful logons immediately followed by password or MFA changes, mailbox rule creation, or impossible-travel alerts for the same account within minutes.
- WAF/bot-management flags distributed requests with identical user-agent strings, headless-browser markers, or known credential-stuffing tool signatures.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Separate spray from stuffing: stuffing reuses many passwords per username from breach corpora; confirm by checking whether the attempted passwords appear in public breach datasets. Then: For each successful post-stuffing logon, inventory session actions: read mail rules, forwarding addresses, OAuth grants, and API keys created in the 24 hours after compromise.
4. **Contain and harden.** Enforce MFA everywhere and block legacy/basic authentication; stuffing dies against phishing-resistant MFA. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking single IPs is whack-a-mole against botnets; block on behavior (velocity, fingerprint) rather than address.
- Forcing a fleet-wide password reset without confirming which accounts were actually taken over burns goodwill and teaches users to pick weaker passwords.

## References

- MITRE ATT&CK: T1110.004 (Credential Access: Brute Force: Credential Stuffing)
- Vendor logging and hardening baselines for AWS Accounts; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
