---
skill_id: cyber_b3_kubernetes_rbac_abuse_hyperv_host_remote_workforce_managed
name: Kubernetes RBAC Abuse Defense for Hyper-V Hosts in Remote Workforce (Managed Maturity)
description: "Kubernetes RBAC Abuse defense playbook for Hyper-V Hosts in Remote Workforce at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, virtualization, hyperv, windows, remote, endpoint, zero-trust, maturity-managed]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for Hyper-V Hosts in Remote Workforce (Managed Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to Hyper-V Hosts in Remote Workforce at Managed maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for Hyper-V Hosts; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
