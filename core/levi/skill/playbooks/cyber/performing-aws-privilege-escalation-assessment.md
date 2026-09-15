---
skill_id: cyber_performing_aws_privilege_escalation_assessment
name: Assessing AWS Privilege Escalation Paths (Defensive)
description: Find and remediate IAM privilege escalation paths in your own AWS accounts.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud-security, aws, iam]
version: 1.0.0
---

## Purpose
Overly permissive IAM policies create paths for privilege escalation: a low-privilege role that can attach admin policies, update Lambda code, or pass roles it should not hold. This defensive playbook finds those paths in your own AWS accounts and remediates them. It does not teach exploitation.

## When to use
- Auditing IAM for escalation risks in your AWS Organization.
- After an incident involving IAM abuse or unexpected privilege use.
- Validating least-privilege before a compliance assessment.

## Prerequisites
- Read-only audit access to the accounts in scope, with written authorization.
- Understanding of your IAM baseline: which roles legitimately need administrative-adjacent permissions.
- A remediation owner who can change IAM policies.

## Procedure
1. **Enumerate effective permissions.** For each principal, resolve the full effective policy set including managed policies, permission boundaries, and SCPs — nominal permissions lie; effective permissions matter.
2. **Identify escalation primitives.** Flag dangerous permission combinations: `iam:Attach*Policy`, `iam:PutRolePolicy`, `lambda:UpdateFunctionCode` with role-passing, `ec2:RunInstances` with instance-profile passing, and similar patterns documented in cloud-security research.
3. **Map the paths.** Trace which low-privilege principals can reach administrative effective permissions through these primitives; prioritize paths reachable by broadly-assumed roles.
4. **Validate carefully in a lab.** Confirm the path exists using a non-production account with equivalent policy — never demonstrate escalation in production.
5. **Remediate by least privilege.** Remove the dangerous permissions, scope them with resource and condition constraints, or redesign the workflow that required them; prefer permission boundaries and SCPs as guardrails.
6. **Add detective controls.** Alert on use of escalation primitives (CloudTrail events for policy attachment, role assumption anomalies) even after remediation.
7. **Re-assess on IAM change.** Run the assessment on a schedule and on every significant IAM change; IAM drifts toward permissiveness by default.

8. **Review cross-account roles.** Trust policies on roles are as important as the permissions attached; an over-broad trust policy is itself a privilege-escalation path.
9. **Automate the assessment.** Codify the escalation-primitive checks so they run on every IAM change via CI or Config rules, not just during annual audits.

## Expected outputs
- Privilege-escalation path inventory with affected principals and remediation priority.
- Remediated policies with guardrails (boundaries, SCPs) preventing recurrence.
- CloudTrail detections for escalation-primitive usage.
- Example: a developer role with `iam:PassRole` plus `lambda:UpdateFunctionCode` is found to reach admin-effective permissions; the fix scopes both permissions with resource constraints and adds a CloudTrail alert on their use.

## Pitfalls
- Testing escalation techniques in production accounts.
- Reviewing attached policies without resolving effective permissions through boundaries and SCPs.
- One-time cleanup with no change-time review: the paths grow back.

## References
- AWS IAM best practices (docs.aws.amazon.com/IAM).
- MITRE ATT&CK T1078 (Valid Accounts) and cloud privilege-escalation technique mappings.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
