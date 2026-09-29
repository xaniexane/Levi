---
skill_id: cyber_b3_kubernetes_rbac_abuse_container_registry_aws_cloud_defined
name: Kubernetes RBAC Abuse Defense for Container Registries in AWS Cloud (Defined Maturity)
description: "Kubernetes RBAC Abuse defense playbook for Container Registries in AWS Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, supply-chain, cloud, aws, maturity-defined]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for Container Registries in AWS Cloud (Defined Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to Container Registries in AWS Cloud at Defined maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: push/pull audit logs + image-scan results + signature verification logs. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push/pull audit log (who pushed which tag/digest, who pulled it, from where) and Vulnerability scan results per image; signature (cosign/Notary) verification outcomes; run `reg audit log --since 7d --action push | head -30` then `reg scan results --image <image:tag> --severity high,critical`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: Image signing required, immutable tags for releases, vulnerability gates blocking critical CVEs. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for Container Registries; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
