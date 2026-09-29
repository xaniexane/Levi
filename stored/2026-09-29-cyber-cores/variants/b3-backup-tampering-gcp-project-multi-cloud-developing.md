---
skill_id: cyber_b3_backup_tampering_gcp_project_multi_cloud_developing
name: Backup Tampering Defense for GCP Projects in Multi-Cloud (Developing Maturity)
description: "Backup Tampering defense playbook for GCP Projects in Multi-Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, cloud, gcp, multi-cloud, maturity-developing]
version: 1.0.0
---
# Backup Tampering Defense for GCP Projects in Multi-Cloud (Developing Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to GCP Projects in Multi-Cloud at Developing maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Cloud Audit Logs: setIamPolicy, storage.setIamPermissions, compute inserts, and console logons and Security Command Center findings; Forseti/Config Validator drift reports where deployed; run `gcloud logging read 'protoPayload.methodName:"SetIamPolicy"' --limit 20 --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, resourceName)'` then `gcloud scc findings list organizations/$ORG_ID --filter='state="ACTIVE"' --limit 15`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for GCP Projects; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
