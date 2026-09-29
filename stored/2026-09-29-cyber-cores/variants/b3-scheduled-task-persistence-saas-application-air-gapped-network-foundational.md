---
skill_id: cyber_b3_scheduled_task_persistence_saas_application_air_gapped_network_foundational
name: Scheduled Task Persistence Defense for SaaS Applications in Air-Gapped Networks (Foundational Maturity)
description: "Scheduled Task Persistence defense playbook for SaaS Applications in Air-Gapped Networks at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, cloud, saas, identity, air-gap, ot, high-security, maturity-foundational]
version: 1.0.0
---
# Scheduled Task Persistence Defense for SaaS Applications in Air-Gapped Networks (Foundational Maturity)

## Purpose

Scheduled tasks are the most common Windows persistence: they survive reboots, run as SYSTEM, and hide among thousands of legitimate tasks. Hunt for tasks with odd actions, odd principals, or creation outside change windows. Applies to SaaS Applications in Air-Gapped Networks at Foundational maturity.

## When to use

- 4698 (scheduled task created) with actions pointing at temp directories, encoded PowerShell, or LOLBins, especially running as SYSTEM.
- Tasks with misleading names mimicking legitimate ones (e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks created outside maintenance windows.
- Task XML in C:\Windows\System32\Tasks with recent timestamps but no corresponding change record.
- Lens: Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Admin audit log (settings changes, user provisioning, sharing changes) and User activity logs: file access, downloads, external sharing events; run `# conceptually (SaaS APIs differ):` then `saas-cli audit log --category admin --last 7d --format table | head -25`.
3. **Analyze.** Export the task XML and inspect actions, triggers, principals, and conditions — the full task definition is the evidence. Then: Determine creation vector: who/what created it (user, GPO, remote RPC) to find the still-active access path.
4. **Contain and harden.** Alert on 4698/4702 fleet-wide; restrict task creation rights and audit tasks running as SYSTEM quarterly. Asset layer: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the task but leaving the payload binary — many implants re-create their task on next execution.
- Trusting the task name; always inspect the action path and hash.

## References

- MITRE ATT&CK: T1053.005 (Persistence: Scheduled Task)
- Vendor logging and hardening baselines for SaaS Applications; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
