---
skill_id: cyber_b3_gpo_abuse_code_repository_aws_cloud_developing
name: Group Policy Abuse Defense for Code Repositories in AWS Cloud (Developing Maturity)
description: "Group Policy Abuse defense playbook for Code Repositories in AWS Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, persistence, devops, supply-chain, secrets, cloud, aws, maturity-developing]
version: 1.0.0
---
# Group Policy Abuse Defense for Code Repositories in AWS Cloud (Developing Maturity)

## Purpose

Group Policy deploys to every machine in scope — including attacker-planted scheduled tasks, scripts, and software. A malicious GPO is a domain-wide persistence and execution platform; monitor GPO changes like code deployments. Applies to Code Repositories in AWS Cloud at Developing maturity.

## When to use

- 5136/5137 directory-service changes creating or modifying GPOs, especially new immediate scheduled tasks, startup scripts, or software installation policies.
- SYSVOL replication of unexpected scripts/executables, or GPO version number jumps without a change ticket.
- Mass host behavior change correlating with GP refresh cycles (new persistence appearing fleet-wide simultaneously).
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Inspect the GPO's full settings and linked scripts; determine the deployment scope (which OUs) to size the affected fleet. Then: Check GPO backup/version history to find when the malicious change was introduced and by whom.
4. **Contain and harden.** Restrict GPO edit rights to a break-glass group, require change tickets, and alert on any GPO modification in real time. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the malicious GPO without removing the persistence it already deployed to thousands of hosts.
- Missing GPO-based deployment because you hunted only local persistence mechanisms.

## References

- MITRE ATT&CK: T1484.001 (Persistence: Domain Policy Modification: Group Policy Modification)
- Vendor logging and hardening baselines for Code Repositories; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
