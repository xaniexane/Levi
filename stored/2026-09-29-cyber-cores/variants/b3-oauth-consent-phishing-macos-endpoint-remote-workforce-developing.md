---
skill_id: cyber_b3_oauth_consent_phishing_macos_endpoint_remote_workforce_developing
name: OAuth Consent Phishing Defense for macOS Endpoints in Remote Workforce (Developing Maturity)
description: "OAuth Consent Phishing defense playbook for macOS Endpoints in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, macos, endpoint, remote, zero-trust, maturity-developing]
version: 1.0.0
---
# OAuth Consent Phishing Defense for macOS Endpoints in Remote Workforce (Developing Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to macOS Endpoints in Remote Workforce at Developing maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for macOS Endpoints; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
