---
skill_id: cyber_detecting_suspicious_oauth_application_consent
name: Detecting Suspicious OAuth Application Consent
description: Detect malicious OAuth app consent grants (illicit consent / app phishing).
risk: low
permissions: []
requires_confirmation: false
tags: [oauth, identity, detection]
version: 1.0.0
---
## Purpose

Illicit consent attacks trick users into granting a malicious OAuth application broad permissions — then the attacker accesses data via API with no malware and no password. This playbook covers detecting suspicious consent grants in identity-provider logs and hardening the consent model.

## When to use

- Users report suspicious 'permissions requested' prompts.
- You need detection for OAuth-based persistence and data access.
- A phishing campaign used fake OAuth consent screens.
- Auditing third-party app access to your tenant.

## Prerequisites

- IdP audit logs of application consent grants (Entra ID audit logs, Google Workspace OAuth token audit).
- Inventory of approved/registered applications and their normal permission scopes.
- Consent policy configuration knowledge (who may consent to what).
- User-reported phishing feed for correlation.

## Procedure

1. Know the illicit-consent pattern. Attack flow: user clicks a phishing link → sees a convincing OAuth consent prompt for an attacker-registered app → grants permissions (often Mail.Read, Files.Read.All, or full mailbox) → attacker accesses data via API indefinitely. Detection focuses on the grant event and the app's subsequent API behavior — the phishing click itself may be invisible to you.
2. Alert on suspicious grant characteristics. Flag consent grants for apps that are: newly registered (especially with names mimicking legitimate services — 'Zoom Meeting', 'DocuSign'), requesting high-privilege or broad scopes (Mail.ReadWrite, Files.ReadWrite.All, Directory.Read.All), consented to by users outside the app's expected audience, or published by unverified publishers. Multi-tenant apps requesting tenant-wide admin consent deserve immediate review.
3. Detect post-consent abuse. A malicious app's API behavior differs from legitimate apps: alert on bulk mailbox/file reads via Graph/API immediately after consent, consent grants followed by data-access spikes, apps accessing data of users who didn't consent (over-broad grants), and apps active only in short bursts (smash-and-grab exfiltration). Correlate consent events with subsequent API audit logs.
4. Hunt existing malicious grants. Periodically review all consented applications: unverified publishers, apps with no legitimate business purpose, grants by users who've since reported phishing, and apps with dormant-then-active patterns. Illicit consent grants persist quietly — scheduled audits catch what real-time alerts miss, especially grants made before alerting existed.
5. Respond by revoking and scoping. Revoke the malicious application's grants tenant-wide, block the app, reset credentials of consenting users and revoke their sessions, scope data accessed via the app's permissions (mailbox/file audit logs), and check for additional persistence (mail rules, forwarding) the attacker set via API access.
6. Harden the consent model: restrict user consent to verified publishers and low-risk scopes, require admin consent workflows for everything else, maintain an approved-application catalog, educate users on consent-screen phishing (check publisher verification, beware urgency), and monitor app-registration events (attackers registering apps in your tenant is its own alert).

## Expected outputs

- Consent-grant detections: suspicious app characteristics, high-risk scopes, anomalous audiences.
- Post-consent API-abuse correlation (grant → bulk data access).
- Scheduled malicious-grant audit procedure and findings tracker.
- Consent-policy hardening: admin workflow, verified-publisher restrictions, app catalog.

## Pitfalls

- Users consent to legitimate apps constantly — scope alerts to unverified publishers and high-risk scopes.
- Attackers name apps after trusted brands; publisher verification status matters more than the display name.
- Revoking the grant without scoping API data access leaves the breach unmeasured — always check audit logs.
- Admin-consent workflows that rubber-stamp requests just move the problem — review seriously.
- Consent grants predate your alerting — run the historical audit, don't just enable forward-looking rules.

## References

- Microsoft Learn: Entra ID consent and permissions, illicit consent attack defense; MITRE ATT&CK T1528 (Steal Application Access Token), T1078.004 (Valid Accounts: Cloud Accounts) — https://attack.mitre.org/techniques/T1528/; CISA guidance on OAuth application abuse
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
