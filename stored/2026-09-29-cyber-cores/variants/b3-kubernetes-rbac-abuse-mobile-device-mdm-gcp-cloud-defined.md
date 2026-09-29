---
skill_id: cyber_b3_kubernetes_rbac_abuse_mobile_device_mdm_gcp_cloud_defined
name: Kubernetes RBAC Abuse Defense for Mobile Devices (MDM) in GCP Cloud (Defined Maturity)
description: "Kubernetes RBAC Abuse defense playbook for Mobile Devices (MDM) in GCP Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, mobile, mdm, endpoint, cloud, gcp, maturity-defined]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for Mobile Devices (MDM) in GCP Cloud (Defined Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to Mobile Devices (MDM) in GCP Cloud at Defined maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in MDM device inventory: OS versions, jailbreak/root detections, installed app lists and Mobile threat defense alerts (malicious apps, network attacks, OS tampering); run `# conceptually (MDM APIs differ):` then `mdm-cli devices list --noncompliant --limit 30`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for Mobile Devices (MDM); Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
