---
skill_id: red_password_spraying
name: Password Spraying Test
description: Test authentication endpoints against password spraying using breached and common passwords to validate lockout and detection.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, credentials, brute-force]
version: 1.0.0
team: red
tests_blue: cyber_core_password_spraying
---
# Password Spraying Test

## Purpose

Validate that password spraying — a few common passwords against many accounts — is
detected and thwarted by lockout policy, MFA, and monitoring. This is the most common
real-world initial access technique against SSO and VPN portals, so the test directly
measures resilience to it.

## When to use

- Against in-scope authentication portals (SSO, VPN, webmail, RDP gateways).
- To validate account lockout thresholds and alerting before attackers do.
- After a breach-corpus review suggests employee passwords are compromised.

## Prerequisites

- Authorization naming the exact authentication endpoints; never spray endpoints outside
  the list.
- Agreed password list (common + breach-corpus, no real employee passwords) and rate
  limits that respect lockout policy.
- Service-account exclusion list — never lock out break-glass or service accounts.

## Procedure

1. Enumerate valid usernames first via the approved method (or use the personnel OSINT
   list) — spraying needs targets.
2. Build the spray list: seasonal passwords, company-name variants, and top breach-corpus
   passwords; explicitly exclude the exclusion list.
3. Spray slowly: one password per user per round, with long delays between rounds to stay
   under lockout thresholds — the point is stealth validation, not lockouts.
4. Monitor for detection: does the SIEM alert on distributed failed logons, impossible
   travel, or password-spray patterns?
5. Record any successful authentications immediately, stop, and report — a spray success is
   a critical finding, not a pivot opportunity, until re-authorized.
6. Deliver the spray report: attempts, rate, detection alerts fired (or not), and any
   compromised credentials rotated under supervision.

## Expected outputs

- Spray attempt log with rate and timing.
- Detection assessment: which alerts fired, with timestamps.
- Any compromised credentials (handled per the credential-handling ROE).

## Pitfalls

- Spraying too fast and locking out real users — the agreed rate is a safety control,
  not a suggestion.
- Using real employee passwords from breach data as spray candidates — use generic
  corpus passwords only.
- Continuing to pivot on a sprayed account without fresh authorization — stop and re-
  scope.

## References

- MITRE ATT&CK: Brute Force — Password Spraying (T1110.003).

## Blue-team control under test

This playbook validates their identity monitoring should detect the spray pattern itself
— silent spraying is a SIEM detection gap regardless of whether any password worked.
Paired blue-team counterpart:
`cyber_core_password_spraying`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
