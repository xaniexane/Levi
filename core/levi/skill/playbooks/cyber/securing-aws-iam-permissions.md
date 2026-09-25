---
skill_id: cyber_securing_aws_iam_permissions
name: Securing AWS IAM Permissions
description: Apply least privilege to AWS IAM: audit with Access Analyzer, remove unused access, and guard with boundaries.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, aws, iam]
version: 1.0.0
---
## Purpose
Over-privileged IAM identities are the most common cloud escalation path. This playbook drives least privilege across an AWS organization: discovering what access exists, removing what is unused, right-sizing the rest, and adding preventive guardrails so privilege does not creep back.

## When to use
- Cloud security program kickoff or annual IAM review.
- After an incident involving compromised AWS credentials.
- Pre-compliance audit evidence collection.
- Following organizational changes that orphan roles and users.

## Prerequisites
- Organization-wide IAM inventory: users, roles, policies, and trust relationships.
- IAM Access Analyzer enabled for unused-access and external-access findings.
- CloudTrail logging for actual permission usage analysis.
- Authority to modify policies coordinated with workload owners.

## Procedure
1. Inventory all principals and their attached managed, inline, and boundary policies.
2. Run IAM Access Analyzer to find unused permissions, unused roles, and external access.
3. Analyze CloudTrail with access advisor data: identify permissions granted but never used.
4. Right-size policies: replace wildcards with specific actions and resources; split broad roles by function.
5. Eliminate long-lived access keys where possible; move to IAM Roles Anywhere, instance roles, or SSO.
6. Enforce MFA for human users and privileged role assumption; require it in policy conditions.
7. Add guardrails: permissions boundaries on delegated administration, SCPs blocking dangerous actions (e.g. leaving the organization, disabling CloudTrail).
8. Re-audit on a schedule; track metrics like wildcard-action count and unused-permission percentage.
9. Review Service Control Policies for overly permissive allows at the organization root.
10. Use IAM Access Analyzer policy validation to catch syntax and logic errors before deployment.
11. Establish a quarterly access review where managers re-certify their teams' AWS access.

## Expected outputs
- IAM least-privilege remediation plan per account with before/after policies.
- Guardrail set: boundaries, SCPs, and MFA enforcement.
- Recurring review metrics and schedule.
- SCP review findings and remediation.
- Policy validation results for new or changed policies.
- Quarterly access re-certification records.

## Pitfalls
- Removing permissions without usage analysis breaks production; use access advisor data first.
- `*` resources on data-plane actions (s3:GetObject on `*`) are the classic silent over-grant.
- Service-linked roles and AWS service needs constrain how far you can restrict; document exceptions.
- Trust policies are the other half; a tight permission policy with a loose trust policy is still exposed.
- Policy simulator results differ from real evaluation on resource-based policies; test both.
- Deny statements in SCPs override everything; audit them as carefully as allows.
- Cross-account role chaining can bypass per-account restrictions; map the full chain.
- Federated identities inherit IdP group sprawl; review IdP group memberships, not just AWS policies.

## References
- AWS Documentation: IAM best practices and Access Analyzer.
- CIS Amazon Web Services Foundations Benchmark.
- AWS re:Invent IAM least-privilege guidance (named).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
