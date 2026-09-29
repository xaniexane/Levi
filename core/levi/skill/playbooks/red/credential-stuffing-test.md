---
skill_id: red_credential_stuffing_test
name: Credential Stuffing Test
description: Test whether breached credential pairs work against in-scope logins, validating breach monitoring and MFA coverage.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, credentials, breach]
version: 1.0.0
team: red
tests_blue: cyber_implementing_passwordless_authentication_with_fido2
---
# Credential Stuffing Test

## Purpose

Employees reuse passwords; breach corpora prove it. This test checks a sample of
breached credential pairs against in-scope authentication endpoints to measure real
account-takeover risk — under strict handling rules, with immediate rotation of anything
that works.

## When to use

- When breach-corpus review shows employee emails in known breaches.
- To justify MFA enforcement with empirical compromise data.
- As part of identity-hygiene assessments.

## Prerequisites

- Explicit authorization for credential-stuffing; many ROEs require extra sign-off for
  this technique.
- Credential-handling agreement: pairs tested from an isolated harness, successes
  trigger immediate forced rotation.
- Scope limited to named endpoints; no stuffing against personal or third-party
  accounts.

## Procedure

1. Source breach pairs from the agreed corpus, filtered to in-scope employee identifiers
   only.
2. Build an isolated test harness that attempts logins at a low rate with full logging;
   never use a personal browser or mix with other activity.
3. On any success: stop that account's testing immediately, record the event, and trigger
   the agreed forced-password-reset workflow.
4. Measure detection: did the SIEM flag impossible-travel, new-device, or velocity alerts
   for the attempts?
5. Aggregate statistics only in the report (X of Y sampled pairs worked); never list
   working credentials in deliverables.
6. Recommendations focus on MFA enforcement, breach-monitoring, and password-manager
   rollout.

## Expected outputs

- Aggregate success statistics (no working credentials in the report).
- Detection assessment for stuffing-pattern alerts.
- Forced-rotation records for any compromised accounts.

## Pitfalls

- Testing credentials belonging to out-of-scope or personal accounts — filter strictly
  to in-scope employees.
- Keeping working credentials 'for later phases' — rotate immediately per the ROE.
- High-rate stuffing that triggers fraud controls and locks users out en masse.

## References

- MITRE ATT&CK: Valid Accounts (T1078).
- OWASP: credential stuffing prevention cheat sheet.

## Blue-team control under test

This playbook validates their breach-monitoring and impossible-travel detections are the
controls under test — working pairs that went unnoticed are identity-monitoring
failures. Paired blue-team counterpart:
`cyber_implementing_passwordless_authentication_with_fido2`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
