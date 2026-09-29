---
skill_id: red_browser_credential_theft
name: Browser Credential Theft Test
description: Test browser-stored credential theft to validate browser hardening and password-manager rollout.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, browser, passwords]
version: 1.0.0
team: red
tests_blue: cyber_abusing_dpapi_for_credential_access
---
# Browser Credential Theft Test

## Purpose

Browsers store passwords, cookies, and session tokens — a rich target that bypasses MFA
via stolen sessions. This test measures what browser-stored material is recoverable and
validates the enterprise password-manager and session-security controls.

## When to use

- During credential-access phases on user workstations.
- To build the business case for enterprise password-manager rollout.
- To validate session-timeout and cookie-security policies.

## Prerequisites

- Authorization for test browser profiles; canary credentials and sessions planted.
- Real user profiles only with explicit approval.

## Procedure

1. Plant canary credentials and sessions in test browser profiles (Chrome, Edge, Firefox as
   deployed).
2. With user-context access, extract the Login Data stores and cookie databases using
   authorized tooling.
3. Test session-cookie replay: does the canary session still authenticate (in the lab,
   against canary services)?
4. Record EDR/file-access telemetry during the extraction.
5. Audit the fleet for password-manager deployment vs. browser-stored passwords.
6. Remove all canary material; verify profiles are clean.
7. Deliver the browser-credential risk assessment with password-manager recommendations.

## Expected outputs

- Per-browser extraction feasibility results.
- Session-replay proof (canary services).
- Password-manager coverage gap analysis.

## Pitfalls

- Extracting real users' cookies/sessions without approval — canary profiles first.
- Session replay against production services — canary services only.
- Forgetting Firefox's separate key4.db/key3.db handling — cover all deployed browsers.

## References

- MITRE ATT&CK: Credentials from Password Stores — Credentials from Web Browsers
  (T1555.003).

## Blue-team control under test

This playbook validates their browser credential posture is under test — recoverable
production passwords are the password-manager business case. Paired blue-team
counterpart: `cyber_abusing_dpapi_for_credential_access`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
