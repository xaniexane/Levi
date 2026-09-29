---
skill_id: cyber_b3_kubernetes_rbac_abuse_aws_account_remote_workforce_defined
name: Kubernetes RBAC Abuse Defense for AWS Accounts in Remote Workforce (Defined Maturity)
description: "Kubernetes RBAC Abuse defense playbook for AWS Accounts in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, cloud, aws, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for AWS Accounts in Remote Workforce (Defined Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to AWS Accounts in Remote Workforce at Defined maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for AWS Accounts; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
