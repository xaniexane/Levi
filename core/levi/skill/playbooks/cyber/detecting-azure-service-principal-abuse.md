---
skill_id: cyber_detecting_azure_service_principal_abuse
name: Detecting Azure Service Principal Abuse
description: Detect compromised or malicious Entra service principals with credential, permission, and behavior monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [azure, identity, detection]
version: 1.0.0
---
## Purpose

Catch abuse of Entra ID service principals — the non-human identities attackers love because they're over-permissioned and under-monitored. Detect credential theft, permission misuse, and malicious app registrations before they become tenant-wide compromise.

## When to use

- Hunting for persistence via malicious app registrations or service principal credential abuse.
- Auditing service principal hygiene (secret sprawl, excessive permissions).
- Investigating alerts involving automation identities or OAuth app consent.
- Post-incident scoping when an attacker may have established app-based persistence.

## Prerequisites

- Entra ID audit logs and sign-in logs for service principals centralized in the SIEM/Log Analytics.
- An inventory of service principals: owner, purpose, permissions, credential types.
- Baseline of normal service-principal behavior: source IPs, call patterns, active hours.
- Authority to revoke credentials and remove app registrations on confirmation of abuse.

## Procedure

1. **Inventory and classify every service principal.** List all app registrations and enterprise apps: owner, business purpose, API permissions (especially `Directory.ReadWrite.All`, `RoleManagement.ReadWrite.Directory`, mail read/write), credential type (secret vs. certificate), and credential age. Flag: no owner, excessive permissions, secrets older than a year, and permissions unused in 90 days.
2. **Alert on credential lifecycle anomalies.** In audit logs, alert on: new secrets/certificates added to any service principal (especially high-privilege ones), secrets added outside change windows, and credentials added by users who don't own the app. Attackers establish persistence by adding their own credential to an existing app — this is the signal.
3. **Detect behavioral deviations.** For each significant service principal, baseline: source IPs/ASNs, authentication patterns, and API call mix. Alert on: authentication from new geographies or datacenter ASNs inconsistent with the workload, new API calls (a mail-reading app suddenly calling directory writes), and activity outside the workload's normal hours.
4. **Hunt malicious app registrations and consent grants.** Alert on: new app registrations by non-developer users, apps requesting high-privilege permissions, admin consent granted to new apps, and user consent to apps requesting offline access or mail permissions. Review the app's redirect URIs and publisher — attacker apps use lookalike names and suspicious URIs.
5. **Monitor permission changes.** Alert on: API permission grants to service principals, role assignments (directory roles) to service principals, and Conditional Access exclusions added for service principals. Each of these expands what the identity can do — treat them as privilege changes, not routine admin.
6. **Correlate with the broader attack.** Service principal abuse rarely happens alone. Join anomalies with: the human account that created the app or added the credential (compromised?), concurrent sign-in anomalies, and data-access patterns (mass mail reads, SharePoint downloads). The service principal is often the persistence mechanism for a human-account compromise.
7. **Respond by killing the credential, not just the session.** On confirmation: remove the attacker-added credential immediately, revoke all refresh tokens for the service principal, audit everything the principal accessed during the compromise window, and review the owning human account for compromise. Then fix the hygiene gap that enabled it (secret → certificate, scoped permissions, owner assigned).

## Expected outputs

- A classified service-principal inventory with hygiene findings (ownerless, over-permissioned, stale secrets).
- Detections for credential-addition anomalies, behavioral deviations, malicious apps, and permission changes.
- Credential-kill response runbooks with compromise-window auditing.

## Pitfalls

- No inventory — you can't detect abuse of identities you don't know exist.
- Alerting on service-principal sign-ins without baselines — automation is chatty; deviations matter, not volume.
- Ignoring user-consent grants — the malicious OAuth app path bypasses admin controls.
- Secrets that never rotate — a leaked secret from 2023 is still valid in 2026.
- Treating the service principal as the whole incident — check the human account behind the credential change.

## References

- Microsoft Learn — Entra ID audit logs, service principal sign-in logs, app governance
- MITRE ATT&CK T1136 (Create Account) and T1550.001 (Application Access Token)
- Microsoft Defender for Cloud Apps — OAuth app anomaly policies
- NIST SP 800-63 / 800-207 — non-person entity authentication considerations
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
