---
skill_id: cyber_b3_password_spraying_aws_account_remote_workforce_developing
name: Password Spraying Defense for AWS Accounts in Remote Workforce (Developing Maturity)
description: "Password Spraying defense playbook for AWS Accounts in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, cloud, aws, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# Password Spraying Defense for AWS Accounts in Remote Workforce (Developing Maturity)

## Purpose

Attackers try a small set of common passwords against many usernames, staying under per-account lockout thresholds. It is quieter than stuffing and specifically tuned to evade lockout policies, often running for days or weeks. Applies to AWS Accounts in Remote Workforce at Developing maturity.

## When to use

- A handful of failed logons per account (1-3) spread across hundreds of accounts from one or a few IPs, repeating on a schedule — the classic low-and-slow pattern.
- The same few passwords attempted everywhere (SeasonYear!, Company123, Password1); check by aggregating failed-logon password hashes where your IdP logs them.
- Spray bursts correlated with newly published password lists or timed to holidays/weekends when response is slower.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Reconstruct the spray window: first-seen to last-seen per source IP, and list every account with even one success inside the window — those are confirmed or suspected takeovers. Then: Check whether sprayed accounts share traits (same OU, same onboarding batch, service accounts) to find how the username list was built.
4. **Contain and harden.** Smart lockout (soft lockout with increasing delays) plus alerting on distributed low-volume failures, not just lockouts. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Per-account lockout thresholds alone will not catch spraying; you need cross-account velocity detection.
- Treating one success as an isolated incident misses the campaign — always scope the full spray window.

## References

- MITRE ATT&CK: T1110.003 (Credential Access: Brute Force: Password Spraying)
- Vendor logging and hardening baselines for AWS Accounts; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
