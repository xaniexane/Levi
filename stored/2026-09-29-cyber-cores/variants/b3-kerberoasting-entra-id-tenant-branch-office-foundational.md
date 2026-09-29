---
skill_id: cyber_b3_kerberoasting_entra_id_tenant_branch_office_foundational
name: Kerberoasting Defense for Microsoft Entra ID Tenants in Branch Offices (Foundational Maturity)
description: "Kerberoasting defense playbook for Microsoft Entra ID Tenants in Branch Offices at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, cloud, microsoft, branch, network, maturity-foundational]
version: 1.0.0
---
# Kerberoasting Defense for Microsoft Entra ID Tenants in Branch Offices (Foundational Maturity)

## Purpose

Attackers request service tickets for SPN accounts and crack them offline to recover service-account passwords — no alerts on the DC, because requesting tickets is normal. The defense is making those passwords uncrackable and the requests visible. Applies to Microsoft Entra ID Tenants in Branch Offices at Foundational maturity.

## When to use

- A single account requesting an unusual number of service tickets (4769) with RC4 encryption for many different SPNs in a short window.
- Ticket requests for SPNs from accounts with no business need, or requests at odd hours from a workstation (not a server).
- Subsequent use of a cracked service account: logons from unexpected hosts or privilege changes for that account.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** List every SPN targeted and assess the crackability of each service account's password (length, complexity, age). Then: If a service account was cracked, treat it as full compromise: inventory everything that account could touch.
4. **Contain and harden.** Service accounts: 25+ character random passwords, or better, group Managed Service Accounts (gMSA) with automatic rotation. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the password but leaving the SPN on a weak account — the attacker just roasts it again.
- Missing that the cracked service account may have been used to request MORE tickets (roast chaining).

## References

- MITRE ATT&CK: T1558.003 (Credential Access: Kerberoasting)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
