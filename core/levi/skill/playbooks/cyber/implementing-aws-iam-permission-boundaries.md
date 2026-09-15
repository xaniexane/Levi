---
skill_id: cyber_implementing_aws_iam_permission_boundaries
name: AWS IAM Permission Boundaries
description: Contain delegated IAM administration with permission boundaries that cap maximum privilege.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, iam]
version: 1.0.0
---
## Purpose
Delegating IAM administration (letting teams create their own roles and users) without guardrails is
how privilege escalation happens: a team grants itself AdministratorAccess and nobody notices until
the incident. Permission boundaries set a maximum-permissions ceiling on IAM principals — delegated
admins can grant only what the boundary allows. This playbook implements boundaries so delegation
scales without privilege sprawl.

## When to use
- Enabling self-service IAM for product teams while retaining central security control.
- After findings of excessive IAM privileges or privilege-escalation paths in AWS.
- Multi-account estates using delegated administrator patterns or IAM Identity Center with
  team-managed permission sets.
- Meeting least-privilege requirements for SOC 2, PCI DSS, or FedRAMP on AWS.
- Alongside SCPs: boundaries cap what identity policies can grant; SCPs cap what the account can do.
  Use both.

## Prerequisites
- An IAM delegation model decision: who may create IAM principals (which teams/roles), and in which
  accounts/OUs.
- A boundary policy design per persona (e.g., developer boundary, data-engineer boundary, CI
  boundary) reflecting actual job needs.
- Central IAM admin rights to create and attach boundary policies, and to enforce their use via
  policy.
- CloudTrail logging of IAM actions for auditing delegation (management events enabled).
- A process for boundary change requests: teams will need new permissions over time.

## Procedure
1. **Map current privilege reality.** Audit existing IAM principals for attached managed policies
   like AdministratorAccess or overly broad custom policies. Document what each team actually uses
   (via IAM Access Analyzer / last-accessed data) — the boundary must permit real work or it will be
   bypassed.
2. **Design boundary policies per persona.** Write customer-managed policies defining the maximum
   allowed actions per persona. Be explicit: allow the services the team needs, deny
   privilege-escalation primitives (iam:*, organizations:*, and dangerous combos like iam:PassRole
   with ec2:RunInstances unless genuinely needed). Deny sts:AssumeRole to highly privileged roles
   outside the boundary's intent.
3. **Enforce boundary attachment.** Apply an SCP or IAM permissions policy requiring that every new
   user/role created by delegated admins has a permissions boundary attached (condition on
   iam:PermissionsBoundary). Without enforcement, boundaries are optional and will be skipped.
4. **Migrate existing principals.** Attach appropriate boundaries to existing team-created
   roles/users. Do this in audit mode first where possible: use IAM Access Analyzer policy
   validation and last-accessed data to confirm the boundary won't break workloads, then attach
   during maintenance windows.
5. **Test escalation paths.** For each persona, attempt (in a test account) the classic escalations:
   creating an admin user, attaching AdministratorAccess, assuming privileged roles, modifying the
   boundary itself. The boundary must block all of them — verify, don't assume.
6. **Separate boundary administration.** Only the central security/IAM team may create or modify
   boundary policies. Delegated admins get iam:CreateUser/Role but never iam:PutPermissionsBoundary
   on their own principals or the ability to edit boundary policies — that's the whole point.
7. **Monitor boundary events.** Alert on: iam:PutUserPermissionsBoundary /
   iam:PutRolePermissionsBoundary calls, attempts to create principals without boundaries (denied by
   your enforcement), and iam:DeleteUserPermissionsBoundary. These are high-signal events for the
   SOC.
8. **Review boundaries quarterly.** Compare boundary permissions against actual usage (Access
   Analyzer unused-access findings). Tighten where usage is consistently narrower; expand through
   the change process where teams are blocked. Boundaries should shrink over time, not grow.
9. **Document the delegation contract.** Publish: which teams can delegate what, the boundary
   catalog, the change-request process, and the escalation test results. Auditors and new team
   members both need this document.
10. **Combine with SCPs and Access Analyzer.** Boundaries cap identity policies; SCPs cap the
    account; Access Analyzer flags unused and external access. Report the three together as the AWS
    least-privilege control set.

## Expected outputs
- Persona-based boundary policies deployed and enforced on all delegated IAM principals.
- Enforcement mechanism (SCP/policy condition) requiring boundary attachment.
- Escalation-path test results proving boundaries hold.
- Monitoring/alerting on boundary lifecycle events.
- Quarterly review cadence with usage-based tightening.

## Pitfalls
- Boundaries that are too tight on day one: teams can't work, shadow accounts appear. Base initial
  boundaries on measured usage, then tighten.
- Forgetting service-linked roles and CI principals: automation breaks loudly when boundaries block
  needed actions — include CI personas in the design.
- Allowing delegated admins to modify boundaries: one iam:PutRolePermissionsBoundary permission
  given loosely voids the entire control.
- Confusing boundaries with SCPs: a boundary never grants access — the identity policy must still
  allow the action. Teams need both layers explained or they'll misdiagnose denials.
- No monitoring: boundaries are preventive, but attempts to circumvent them are detective gold — log
  and alert.

## References
- AWS IAM documentation: Permissions boundaries for IAM entities
- AWS IAM Access Analyzer documentation (unused access, policy validation)
- NIST SP 800-53 AC-6 (least privilege)
- MITRE ATT&CK T1078 (Valid Accounts), T1484 (Domain Policy Modification) — privilege paths
  boundaries constrain
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
