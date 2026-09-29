---
skill_id: cyber_b3_wmi_persistence_entra_id_tenant_remote_workforce_foundational
name: WMI Persistence Defense for Microsoft Entra ID Tenants in Remote Workforce (Foundational Maturity)
description: "WMI Persistence defense playbook for Microsoft Entra ID Tenants in Remote Workforce at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, identity, cloud, microsoft, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# WMI Persistence Defense for Microsoft Entra ID Tenants in Remote Workforce (Foundational Maturity)

## Purpose

WMI event subscriptions trigger payloads on system events (timers, logons) with no visible scheduled task or service. They are fileless, stealthy, and missed by autorun tools that do not enumerate the WMI repository. Applies to Microsoft Entra ID Tenants in Remote Workforce at Foundational maturity.

## When to use

- New __EventFilter/__EventConsumer/__FilterToConsumerBinding instances in the WMI repository, especially ActiveScript or CommandLine consumers with encoded commands.
- WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI operational log entries for subscription creation.
- Persistence that survives task/service cleanup — the classic sign the mechanism is WMI-based.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Enumerate all event subscriptions (Get-WMIObject -Namespace root\subscription) and inspect each consumer's command line. Then: Correlate subscription creation time with the initial compromise to confirm it is attacker-planted, not admin tooling.
4. **Contain and harden.** Alert on WMI subscription creation events; restrict WMI namespace permissions to administrators. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring a host clean after checking tasks/services/registry but never looking at WMI subscriptions.
- Removing the consumer but leaving the filter and binding, which error silently and get recreated by the implant.

## References

- MITRE ATT&CK: T1047 (Execution: Windows Management Instrumentation)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
