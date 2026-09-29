---
skill_id: cyber_b3_kubernetes_rbac_abuse_wifi_controller_on_prem_datacenter_defined
name: Kubernetes RBAC Abuse Defense for Wireless Controllers in On-Premises Datacenter (Defined Maturity)
description: "Kubernetes RBAC Abuse defense playbook for Wireless Controllers in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, network, wireless, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for Wireless Controllers in On-Premises Datacenter (Defined Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to Wireless Controllers in On-Premises Datacenter at Defined maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Client association, authentication (EAP) and roaming logs with device MACs and Rogue AP / evil-twin detections and deauth-flood alerts from WIDS; run `# conceptually (vendor CLIs differ):` then `show wireless client summary | include <suspect-mac>`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for Wireless Controllers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
