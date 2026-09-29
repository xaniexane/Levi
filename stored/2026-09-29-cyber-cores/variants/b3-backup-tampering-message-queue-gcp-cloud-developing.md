---
skill_id: cyber_b3_backup_tampering_message_queue_gcp_cloud_developing
name: Backup Tampering Defense for Message Queues in GCP Cloud (Developing Maturity)
description: "Backup Tampering defense playbook for Message Queues in GCP Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, messaging, application, cloud, gcp, maturity-developing]
version: 1.0.0
---
# Backup Tampering Defense for Message Queues in GCP Cloud (Developing Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Message Queues in GCP Cloud at Developing maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues and Authentication logs for producers/consumers; new queue/topic creation events; run `rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20` then `kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Message Queues; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
