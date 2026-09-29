---
skill_id: cyber_b3_kerberoasting_identity_provider_sso_remote_workforce_optimized
name: Kerberoasting Defense for SSO Identity Providers in Remote Workforce (Optimized Maturity)
description: "Kerberoasting defense playbook for SSO Identity Providers in Remote Workforce at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, sso, authentication, remote, endpoint, zero-trust, maturity-optimized]
version: 1.0.0
---
# Kerberoasting Defense for SSO Identity Providers in Remote Workforce (Optimized Maturity)

## Purpose

Attackers request service tickets for SPN accounts and crack them offline to recover service-account passwords — no alerts on the DC, because requesting tickets is normal. The defense is making those passwords uncrackable and the requests visible. Applies to SSO Identity Providers in Remote Workforce at Optimized maturity.

## When to use

- A single account requesting an unusual number of service tickets (4769) with RC4 encryption for many different SPNs in a short window.
- Ticket requests for SPNs from accounts with no business need, or requests at odd hours from a workstation (not a server).
- Subsequent use of a cracked service account: logons from unexpected hosts or privilege changes for that account.
- Lens: Best telemetry: authentication logs with MFA detail + app-assignment changes + federation trust changes. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Authentication logs per application (success/failure, MFA method, device, location) and Application assignment and provisioning logs; new SSO integrations; run `# conceptually (IdP APIs differ):` then `idp-cli logs auth --user <upn> --last 7d --format table | head -25`.
3. **Analyze.** List every SPN targeted and assess the crackability of each service account's password (length, complexity, age). Then: If a service account was cracked, treat it as full compromise: inventory everything that account could touch.
4. **Contain and harden.** Service accounts: 25+ character random passwords, or better, group Managed Service Accounts (gMSA) with automatic rotation. Asset layer: Phishing-resistant MFA default, sign-on policies per app risk, session lifetime limits. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the password but leaving the SPN on a weak account — the attacker just roasts it again.
- Missing that the cracked service account may have been used to request MORE tickets (roast chaining).

## References

- MITRE ATT&CK: T1558.003 (Credential Access: Kerberoasting)
- Vendor logging and hardening baselines for SSO Identity Providers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
