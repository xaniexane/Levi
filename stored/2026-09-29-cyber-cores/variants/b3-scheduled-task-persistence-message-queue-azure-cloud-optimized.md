---
skill_id: cyber_b3_scheduled_task_persistence_message_queue_azure_cloud_optimized
name: Scheduled Task Persistence Defense for Message Queues in Azure Cloud (Optimized Maturity)
description: "Scheduled Task Persistence defense playbook for Message Queues in Azure Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, messaging, application, cloud, azure, maturity-optimized]
version: 1.0.0
---
# Scheduled Task Persistence Defense for Message Queues in Azure Cloud (Optimized Maturity)

## Purpose

Scheduled tasks are the most common Windows persistence: they survive reboots, run as SYSTEM, and hide among thousands of legitimate tasks. Hunt for tasks with odd actions, odd principals, or creation outside change windows. Applies to Message Queues in Azure Cloud at Optimized maturity.

## When to use

- 4698 (scheduled task created) with actions pointing at temp directories, encoded PowerShell, or LOLBins, especially running as SYSTEM.
- Tasks with misleading names mimicking legitimate ones (e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks created outside maintenance windows.
- Task XML in C:\Windows\System32\Tasks with recent timestamps but no corresponding change record.
- Lens: Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues and Authentication logs for producers/consumers; new queue/topic creation events; run `rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20` then `kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20`.
3. **Analyze.** Export the task XML and inspect actions, triggers, principals, and conditions — the full task definition is the evidence. Then: Determine creation vector: who/what created it (user, GPO, remote RPC) to find the still-active access path.
4. **Contain and harden.** Alert on 4698/4702 fleet-wide; restrict task creation rights and audit tasks running as SYSTEM quarterly. Asset layer: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the task but leaving the payload binary — many implants re-create their task on next execution.
- Trusting the task name; always inspect the action path and hash.

## References

- MITRE ATT&CK: T1053.005 (Persistence: Scheduled Task)
- Vendor logging and hardening baselines for Message Queues; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
