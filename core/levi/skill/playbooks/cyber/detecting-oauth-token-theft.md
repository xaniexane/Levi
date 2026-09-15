---
skill_id: cyber_detecting_oauth_token_theft
name: Detecting OAuth Token Theft
description: Detect theft and abuse of OAuth access and refresh tokens.
risk: low
permissions: []
requires_confirmation: false
tags: [oauth, identity, detection]
version: 1.0.0
---
## Purpose

OAuth tokens are bearer credentials: whoever holds the token has the access, no password needed. Token theft — via XSS, malicious apps, log leakage, or endpoint compromise — lets attackers impersonate users and apps against cloud APIs. This playbook covers detecting stolen-token usage through identity-provider logs, token-replay anomalies, and API telemetry.

## When to use

- Your IdP (Entra ID, Okta, Google) shows impossible-travel or anomalous API activity.
- An application logged tokens in plaintext and you need to assess abuse.
- Threat intel describes token-theft campaigns targeting your sector.
- Building detection for OAuth-based persistence and API abuse.

## Prerequisites

- IdP sign-in and audit logs (Entra ID sign-in logs, Okta System Log) with IP, device, location, and app/client identifiers.
- API/resource access logs showing which tokens access what data (Microsoft Graph audit, Google Workspace audit, SaaS audit logs).
- Inventory of registered OAuth applications, their permission scopes, and owners.
- Baseline of normal token usage: expected IPs/devices per user, normal apps per user.

## Procedure

1. Detect token replay across contexts. The core signal: the same user/app token used from inconsistent contexts — different IPs, geographies, devices, or user-agents within implausible time windows. Alert on impossible-travel for API-authenticated sessions (not just interactive logons), and on a single token/user appearing from both a corporate device and an unknown VPS within minutes.
2. Watch for scope and API abuse. A stolen token gets used for what the thief wants, not what the app does: alert on API calls outside the application's normal pattern (e.g., a calendar app suddenly reading all mail, or Graph calls enumerating users/groups), and on bulk read operations (mailbox enumeration, file downloads) inconsistent with the app's purpose.
3. Monitor refresh-token anomalies. Refresh tokens are long-lived and prized: alert on refresh-token reuse from different IPs (indicates token sharing/theft), unexpected refresh-token grant locations, and password-change or MFA-reset events followed by continued API access from old sessions (stale token still valid).
4. Hunt token leakage sources. Tokens get stolen from: browser local storage via XSS, mobile app logs, CI/CD secrets, and leaked HTTP logs. When theft is confirmed, find the leak — review the application's token storage, check for tokens in logs (search log stores for JWT-shaped strings), and audit app registrations for overly broad redirect URIs.
5. Respond decisively: revoke the compromised tokens and sessions immediately (IdP session revocation), rotate the application's client secret, investigate data accessed via the token (API audit logs), reset the user's credentials and re-verify MFA, and remove malicious app consents. Then fix the leak that enabled the theft.
6. Harden token handling: enforce short token lifetimes, use continuous access evaluation (CAE) where supported, require phishing-resistant MFA, restrict app permissions to least privilege, and monitor app-registration and consent-grant events as their own detection use case.

## Expected outputs

- Token-replay detections: impossible-travel on API sessions, cross-context token use, refresh-token anomalies.
- API-abuse detections: out-of-pattern calls per app, bulk-read anomalies.
- Token-leak hunting procedure: log searches, app storage review, redirect-URI audit.
- Revocation and rotation runbook with data-access scoping steps.

## Pitfalls

- Tokens are bearer credentials — 'valid token from a new IP' is often the only signal; don't wait for malware.
- Legitimate users roam (VPNs, travel); tune impossible-travel with VPN egress and travel data.
- Service principals and automation generate high API volumes — baseline per app, not per user.
- Revoking tokens without fixing the leak (XSS, logged tokens) just starts the clock on the next theft.
- Some IdPs delay audit-log ingestion; account for latency in 'real-time' detections.

## References

- Microsoft Learn: Entra ID sign-in logs, token protection, Continuous Access Evaluation; MITRE ATT&CK T1528 (Steal Application Access Token) — https://attack.mitre.org/techniques/T1528/; OAuth 2.0 Security Best Current Practice (IETF)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
