---
skill_id: cyber_b3_scheduled_task_persistence_entra_id_tenant_azure_cloud_managed
name: Scheduled Task Persistence Defense for Microsoft Entra ID Tenants in Azure Cloud (Managed Maturity)
description: "Scheduled Task Persistence defense playbook for Microsoft Entra ID Tenants in Azure Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, identity, cloud, microsoft, azure, maturity-managed]
version: 1.0.0
---
# Scheduled Task Persistence Defense for Microsoft Entra ID Tenants in Azure Cloud (Managed Maturity)

## Purpose

Scheduled tasks are the most common Windows persistence: they survive reboots, run as SYSTEM, and hide among thousands of legitimate tasks. Hunt for tasks with odd actions, odd principals, or creation outside change windows. Applies to Microsoft Entra ID Tenants in Azure Cloud at Managed maturity.

## When to use

- 4698 (scheduled task created) with actions pointing at temp directories, encoded PowerShell, or LOLBins, especially running as SYSTEM.
- Tasks with misleading names mimicking legitimate ones (e.g., 'GoogleUpdateTaskMachineUA' in the wrong path), or tasks created outside maintenance windows.
- Task XML in C:\Windows\System32\Tasks with recent timestamps but no corresponding change record.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Export the task XML and inspect actions, triggers, principals, and conditions — the full task definition is the evidence. Then: Determine creation vector: who/what created it (user, GPO, remote RPC) to find the still-active access path.
4. **Contain and harden.** Alert on 4698/4702 fleet-wide; restrict task creation rights and audit tasks running as SYSTEM quarterly. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the task but leaving the payload binary — many implants re-create their task on next execution.
- Trusting the task name; always inspect the action path and hash.

## References

- MITRE ATT&CK: T1053.005 (Persistence: Scheduled Task)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
