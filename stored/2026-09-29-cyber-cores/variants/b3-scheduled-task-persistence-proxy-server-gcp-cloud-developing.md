---
skill_id: cyber_b3_scheduled_task_persistence_proxy_server_gcp_cloud_developing
name: Scheduled Task Persistence Defense for Proxy Servers in GCP Cloud (Developing Maturity)
description: "Scheduled Task Persistence defense playbook for Proxy Servers in GCP Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, network, proxy, web, cloud, gcp, maturity-developing]
version: 1.0.0
---
# Scheduled Task Persistence Defense for Proxy Servers in GCP Cloud (Developing Maturity)

## Purpose

Scheduled tasks are the most common Windows persistence: they survive reboots, run as SYSTEM, and hide among thousands of legitimate tasks. Hunt for tasks with odd actions, odd principals, or creation outside change windows. Applies to Proxy Servers in GCP Cloud at Developing maturity.

## When to use

- 4698 (scheduled task created) with actions pointing at temp directories, encoded PowerShell, or LOLBins, especially running as SYSTEM.
- Tasks with misleading names mimicking legitimate ones (e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks created outside maintenance windows.
- Task XML in C:\Windows\System32\Tasks with recent timestamps but no corresponding change record.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Export the task XML and inspect actions, triggers, principals, and conditions — the full task definition is the evidence. Then: Determine creation vector: who/what created it (user, GPO, remote RPC) to find the still-active access path.
4. **Contain and harden.** Alert on 4698/4702 fleet-wide; restrict task creation rights and audit tasks running as SYSTEM quarterly. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the task but leaving the payload binary — many implants re-create their task on next execution.
- Trusting the task name; always inspect the action path and hash.

## References

- MITRE ATT&CK: T1053.005 (Persistence: Scheduled Task)
- Vendor logging and hardening baselines for Proxy Servers; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
