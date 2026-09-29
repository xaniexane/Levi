---
skill_id: cyber_b3_oauth_consent_phishing_container_registry_remote_workforce_optimized
name: OAuth Consent Phishing Defense for Container Registries in Remote Workforce (Optimized Maturity)
description: "OAuth Consent Phishing defense playbook for Container Registries in Remote Workforce at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, containers, supply-chain, remote, endpoint, zero-trust, maturity-optimized]
version: 1.0.0
---
# OAuth Consent Phishing Defense for Container Registries in Remote Workforce (Optimized Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to Container Registries in Remote Workforce at Optimized maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: push/pull audit logs + image-scan results + signature verification logs. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push/pull audit log (who pushed which tag/digest, who pulled it, from where) and Vulnerability scan results per image; signature (cosign/Notary) verification outcomes; run `reg audit log --since 7d --action push | head -30` then `reg scan results --image <image:tag> --severity high,critical`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: Image signing required, immutable tags for releases, vulnerability gates blocking critical CVEs. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for Container Registries; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
