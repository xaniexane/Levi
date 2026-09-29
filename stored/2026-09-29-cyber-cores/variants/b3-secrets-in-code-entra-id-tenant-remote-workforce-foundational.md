---
skill_id: cyber_b3_secrets_in_code_entra_id_tenant_remote_workforce_foundational
name: Secrets in Code Defense for Microsoft Entra ID Tenants in Remote Workforce (Foundational Maturity)
description: "Secrets in Code defense playbook for Microsoft Entra ID Tenants in Remote Workforce at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [devops, secrets, identity, cloud, microsoft, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Secrets in Code Defense for Microsoft Entra ID Tenants in Remote Workforce (Foundational Maturity)

## Purpose

API keys, passwords, and tokens committed to repositories get scraped by attackers (and by every future repo reader). A committed secret is a compromised secret — rotate first, clean history second. Applies to Microsoft Entra ID Tenants in Remote Workforce at Foundational maturity.

## When to use

- Secret-scanning alerts (push protection or historical scan) flagging keys, tokens, or private keys in commits.
- Anomalous API usage billed to a key that appears in a repository, or commits adding '.env' files.
- Public repository exposure: any secret ever pushed public is considered harvested.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** For each exposed secret: determine its privileges and check usage logs for unauthorized use since exposure. Then: Check git history depth: secrets in old commits are still exposed to anyone with repo access.
4. **Contain and harden.** Rotate the secret FIRST, then purge from history; enable push protection and pre-commit secret scanning. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the commit without rotating — the secret is already copied.
- Scanning only main branch; secrets hide in feature branches, PRs, and forks.

## References

- MITRE ATT&CK: T1552.001 (Credential Access: Credentials In Files)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
