---
skill_id: cyber_b3_mfa_fatigue_entra_id_tenant_remote_workforce_optimized
name: MFA Fatigue Attack Defense for Microsoft Entra ID Tenants in Remote Workforce (Optimized Maturity)
description: "MFA Fatigue Attack defense playbook for Microsoft Entra ID Tenants in Remote Workforce at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, cloud, microsoft, remote, endpoint, zero-trust, maturity-optimized]
version: 1.0.0
---
# MFA Fatigue Attack Defense for Microsoft Entra ID Tenants in Remote Workforce (Optimized Maturity)

## Purpose

Attackers with a stolen password spam push notifications until the victim approves one out of annoyance or confusion. The defense is push hygiene: number matching, context display, and rate limits on prompts. Applies to Microsoft Entra ID Tenants in Remote Workforce at Optimized maturity.

## When to use

- Dozens of MFA push prompts to one user in minutes, especially at odd hours, followed by a single approval.
- An approval immediately followed by session activity from an unusual IP or device enrollment changes.
- Helpdesk reports of users 'getting lots of MFA prompts' in the days before the incident.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Reconstruct the prompt storm: count, timing, and the approving event — then inventory the attacker's post-approval actions. Then: Check whether the attacker registered a new MFA method during the session (persistence via second factor).
4. **Contain and harden.** Number matching on all push MFA, show login context (app, location), and rate-limit prompts per user. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming an approved push means a legitimate user — approval is exactly what the attacker engineered.
- Not checking for newly registered MFA methods, which survive password resets.

## References

- MITRE ATT&CK: T1621 (Credential Access: MFA Request Generation)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
