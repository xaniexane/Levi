---
skill_id: red_cloud_oauth_app_persistence
name: Cloud OAuth App Persistence Test
description: Test malicious OAuth application grants as cloud persistence to validate app-consent monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, persistence, cloud, oauth]
version: 1.0.0
team: red
tests_blue: cyber_core_oauth_consent_phishing
---
# Cloud OAuth App Persistence Test

## Purpose

In cloud environments, persistence isn't a registry key — it's an OAuth grant. A
malicious app registration with Mail.Read or full mailbox permissions persists
independently of passwords and MFA. This test measures whether app-consent grants are
monitored and whether malicious apps would be noticed.

## When to use

- During cloud persistence phases (M365, Google Workspace).
- To validate OAuth app governance: who can consent, and what gets flagged.
- After phishing tests, as the 'what if they consented' follow-on.

## Prerequisites

- Explicit authorization for OAuth app registration in the tenant; test tenant
  preferred.
- Agreement on permission scope ceiling for the test app (read-only, canary data).

## Procedure

1. Register a test OAuth application with attention-grabbing but in-test naming; request
   the authorized permission set.
2. Complete the consent flow as the test user; record whether admin consent workflow
   triggered or user consent sufficed.
3. Verify persistence: revoke the user's password session and confirm the app grant still
   provides access (to canary data only).
4. Monitor the blue-team side: did app-registration or consent-grant alerts fire? How fast?
5. Enumerate existing third-party app grants in the tenant as a bonus finding — stale
   grants are the real-world version of this test.
6. Delete the test app and revoke all grants; verify removal in audit logs.

## Expected outputs

- Consent-flow control assessment (user vs. admin consent).
- App-registration detection timeline.
- Stale third-party grant inventory (bonus finding).
- Cleanup verification with audit-log evidence.

## Pitfalls

- Requesting excessive permissions 'for realism' — stay within the agreed ceiling.
- Testing in the production tenant without explicit approval — prefer the test tenant.
- Leaving the app registered — revocation is verified, not assumed.

## References

- MITRE ATT&CK: Valid Accounts — Cloud Accounts (T1078.004); OAuth abuse literature
  (public).

## Blue-team control under test

This playbook validates their OAuth app governance and consent-grant monitoring are
under test — unalerted app registrations are an identity-governance gap. Paired blue-
team counterpart:
`cyber_core_oauth_consent_phishing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
