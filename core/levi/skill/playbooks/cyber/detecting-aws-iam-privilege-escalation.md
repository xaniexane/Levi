---
skill_id: cyber_detecting_aws_iam_privilege_escalation
name: Detecting AWS IAM Privilege Escalation
description: Detect IAM privilege-escalation paths and active exploitation with policy analysis and CloudTrail monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, iam, detection]
version: 1.0.0
---
## Purpose

Catch privilege escalation in AWS IAM — both the misconfigurations that enable it and the active exploitation: policy attachments, role assumptions, and the classic escalation primitives. IAM is the control plane; escalation here is game over.

## When to use

- Auditing IAM for escalation paths before attackers find them.
- Monitoring CloudTrail for active privilege-escalation attempts.
- Investigating a compromised low-privilege principal that may have escalated.
- Validating least-privilege after IAM refactors.

## Prerequisites

- Read access to IAM policies, roles, and trust relationships across accounts.
- CloudTrail organization trail with Athena/SIEM querying.
- A tool for escalation-path analysis (Pacu's iam__privesc_scan for authorized testing, or static policy analyzers).
- Baseline of normal administrative IAM activity (who legitimately changes policies).

## Procedure

1. **Inventory escalation primitives in your policies.** Map which principals hold dangerous permissions: `iam:*` on resources, `iam:PassRole` + service creation rights, `sts:AssumeRole` on powerful roles, `lambda:CreateFunction` + `iam:PassRole`, and `ec2:RunInstances` + instance-profile pass. Document each as a finding with the blast radius — this is your escalation-path register.
2. **Analyze role trust relationships.** Review every role's trust policy: overly broad principals (`*` or entire accounts), trust on external IDs that are guessable, and roles trustable by compromised-prone services. A powerful role with a sloppy trust policy is an escalation waiting for a confused-deputy or stolen credential.
3. **Alert on policy-modification APIs.** In CloudTrail, alert on: `AttachUserPolicy`, `AttachRolePolicy`, `PutUserPolicy`, `PutRolePolicy`, `CreatePolicyVersion` (especially setting a new version as default), and `UpdateAssumeRolePolicy`. Baseline the legitimate changers (your IaC pipeline, specific admins) and treat anything else as high severity.
4. **Alert on anomalous role assumption.** Flag `sts:AssumeRole` where: the role was never assumed by this principal before, the assumption comes from a new source IP/ASN, or the role is administrative. Chain with the recon signals — `GetCallerIdentity` + `List*` followed by `AssumeRole` to an admin role is the classic escalation sequence.
5. **Detect the known escalation techniques.** Monitor for: new access keys created on other users (`CreateAccessKey` for a different username), login profiles created (`CreateLoginProfile`), policy version rollbacks to permissive versions, and Lambda/EC2-based escalation (function created with an admin role passed to it, then invoked). Map each to the corresponding escalation primitive from step 1.
6. **Hunt dormant escalation paths.** Query for principals that haven't used their dangerous permissions in 90+ days — these are the paths attackers will use because nobody watches them. Either remove the permissions or put them under explicit monitoring. Unused admin rights are just attacker options.
7. **Respond by breaking the path, not just the session.** On confirmed escalation: revoke the sessions (not just rotate keys — kill active sessions), remove the exploited permission or fix the trust policy, and audit everything the escalated principal touched. Escalation response that leaves the path open invites round two.

## Expected outputs

- An escalation-path register mapping dangerous permissions and trust relationships to blast radius.
- CloudTrail alerts on policy modification, anomalous role assumption, and known escalation techniques.
- Dormant-permission hunting with removal or explicit monitoring; path-breaking incident response.

## Pitfalls

- Auditing policies but not trust relationships — the trust policy is half the escalation surface.
- Alerting on `AssumeRole` without baselines — legitimate automation assumes roles constantly; the anomaly is what matters.
- Missing `CreatePolicyVersion` — attackers don't attach new policies, they version the existing one.
- Responding with key rotation only — active sessions survive; revoke sessions and fix the path.
- One-time audits — IAM drifts; the escalation register needs quarterly refresh.

## References

- AWS documentation — IAM best practices, policy evaluation logic, trust policies
- MITRE ATT&CK T1078 (Valid Accounts) and T1552 (Unsecured Credentials) in cloud context
- Pacu documentation (authorized testing of escalation paths)
- NIST SP 800-53 AC-6 (least privilege) and AC-2 (account management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
