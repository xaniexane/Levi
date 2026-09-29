---
skill_id: cyber_b3_backup_tampering_kubernetes_cluster_multi_cloud_foundational
name: Backup Tampering Defense for Kubernetes Clusters in Multi-Cloud (Foundational Maturity)
description: "Backup Tampering defense playbook for Kubernetes Clusters in Multi-Cloud at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, containers, kubernetes, cloud, multi-cloud, maturity-foundational]
version: 1.0.0
---
# Backup Tampering Defense for Kubernetes Clusters in Multi-Cloud (Foundational Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Kubernetes Clusters in Multi-Cloud at Foundational maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in API-server audit log (who created pods/bindings/secrets, from where) and Kubelet/container runtime logs and image pull histories per node; run `kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20` then `kubectl get pods -A -o json | python3 -c "import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]" | head -30`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Kubernetes Clusters; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
