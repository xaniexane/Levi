---
skill_id: red_password_spray_test
name: Password Spraying Test
description: Test password spraying with strict account-safety controls to validate lockout and alerting.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, password-spray]
version: 1.0.0
team: red
tests_blue: cyber_core_password_spraying
---
# Password Spraying Test

## Purpose

Password spraying — one common password across many accounts — dodges per-account
lockouts and finds the weak-password outliers. This carefully controlled test validates
lockout policy, spray detection, and whether any accounts actually fall.

## When to use

- During credential-access phases, with explicit authentication-testing authorization.
- To validate Azure AD / AD spray-detection and smart lockout.
- To prove the weak-password tail exists (or doesn't).

## Prerequisites

- Explicit authorization naming password spraying with attempt ceilings.
- Agreed password list (common, non-targeted), attempt rate, and time window.
- Account allowlist/blocklist: never spray service, admin, or VIP accounts without
  specific approval.

## Procedure

1. Confirm the lockout policy and spray-detection baseline with the blue team before
   starting.
2. Run the spray within the agreed ceiling: one password per round, rounds spaced per the
   agreement.
3. Monitor for lockouts in real time; abort immediately if any unapproved account locks.
4. Record valid credentials per the ROE — verify and hand to the blue team for rotation,
   never retain.
5. Check detection: did the spray trip identity-protection alerts? How many rounds before
   it fired?
6. Deliver the spray assessment: policy effectiveness, detection latency, and the weak-
   password findings.

## Expected outputs

- Spray execution log within agreed ceilings.
- Detection-latency measurement (rounds to alert).
- Weak-credential findings with rotation handoff.

## Pitfalls

- Exceeding the attempt ceiling — the ceiling is the authorization, not a suggestion.
- Spraying without a live lockout monitor — abort capability must be real.
- Retaining discovered credentials beyond the rotation handoff.

## References

- MITRE ATT&CK: Brute Force — Password Spraying (T1110.003).

## Blue-team control under test

This playbook validates their authentication monitoring faces a low-and-slow attack —
silent spraying across many rounds is an identity-protection gap. Paired blue-team
counterpart:
`cyber_core_password_spraying`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
