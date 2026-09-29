---
skill_id: cyber_b3_scheduled_task_persistence_secrets_vault_multi_cloud_foundational
name: Scheduled Task Persistence Defense for Secrets Vaults in Multi-Cloud (Foundational Maturity)
description: "Scheduled Task Persistence defense playbook for Secrets Vaults in Multi-Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, secrets, identity, cloud, multi-cloud, maturity-foundational]
version: 1.0.0
---
# Scheduled Task Persistence Defense for Secrets Vaults in Multi-Cloud (Foundational Maturity)

## Purpose

Scheduled tasks are the most common Windows persistence: they survive reboots, run as SYSTEM, and hide among thousands of legitimate tasks. Hunt for tasks with odd actions, odd principals, or creation outside change windows. Applies to Secrets Vaults in Multi-Cloud at Foundational maturity.

## When to use

- 4698 (scheduled task created) with actions pointing at temp directories, encoded PowerShell, or LOLBins, especially running as SYSTEM.
- Tasks with misleading names mimicking legitimate ones (e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks created outside maintenance windows.
- Task XML in C:\Windows\System32\Tasks with recent timestamps but no corresponding change record.
- Lens: Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Audit log of secret reads/writes/deletes with client identity and source IP and Policy and auth-method changes; root-token generation events; run `vault audit log --since 24h 2>/dev/null | grep -E '"path":"secret' | head -20` then `vault list sys/policy 2>/dev/null; vault auth list 2>/dev/null`.
3. **Analyze.** Export the task XML and inspect actions, triggers, principals, and conditions — the full task definition is the evidence. Then: Determine creation vector: who/what created it (user, GPO, remote RPC) to find the still-active access path.
4. **Contain and harden.** Alert on 4698/4702 fleet-wide; restrict task creation rights and audit tasks running as SYSTEM quarterly. Asset layer: Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the task but leaving the payload binary — many implants re-create their task on next execution.
- Trusting the task name; always inspect the action path and hash.

## References

- MITRE ATT&CK: T1053.005 (Persistence: Scheduled Task)
- Vendor logging and hardening baselines for Secrets Vaults; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
