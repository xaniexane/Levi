---
skill_id: cyber_b3_kubernetes_rbac_abuse_cicd_runner_branch_office_optimized
name: Kubernetes RBAC Abuse Defense for CI/CD Runners in Branch Offices (Optimized Maturity)
description: "Kubernetes RBAC Abuse defense playbook for CI/CD Runners in Branch Offices at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, devops, supply-chain, branch, network, maturity-optimized]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for CI/CD Runners in Branch Offices (Optimized Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to CI/CD Runners in Branch Offices at Optimized maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for CI/CD Runners; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
