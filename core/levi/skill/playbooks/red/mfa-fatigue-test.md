---
skill_id: red_mfa_fatigue_test
name: MFA Fatigue (Push Bombing) Test
description: Test user resistance to MFA push-notification fatigue and validate number-matching and alerting controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, mfa, credentials]
version: 1.0.0
team: red
tests_blue: cyber_core_mfa_fatigue
---
# MFA Fatigue (Push Bombing) Test

## Purpose

After obtaining a password (via spraying or stuffing, as separately authorized), the
next layer is MFA — and push-based MFA can be worn down by repeated prompts. This test
measures whether users approve fraudulent pushes and whether the identity team detects
the anomaly. It is also the test that justifies phishing-resistant MFA.

## When to use

- After a credential is obtained in an earlier phase, to test the MFA layer
  specifically.
- To validate number-matching MFA rollout and anomalous-push alerting.
- When the org still relies on push-approve MFA.

## Prerequisites

- Authorization for MFA-fatigue testing specifically, with a cap on push volume per
  user.
- The compromised credential used must itself have been obtained under authorization.
- User-support plan: targeted users get a debrief, not a surprise.

## Procedure

1. Using the authorized credential, initiate logins that trigger MFA pushes to the target
   user, capped at the agreed volume and window.
2. Vary timing: bursts vs. spread-out prompts, business hours vs. off-hours.
3. Record user responses: approve, deny, ignore — and time-to-response.
4. Monitor identity-team detection in parallel: do repeated pushes trigger risk alerts,
   account lockout, or analyst review?
5. Stop immediately on any approval; an approval is the finding, not an invitation to
   pivot.
6. Debrief the targeted users and deliver the fatigue-resistance assessment with MFA-
   upgrade recommendations.

## Expected outputs

- Per-user push response outcomes (approve/deny/ignore) with timing.
- Identity-team detection assessment for anomalous push patterns.
- MFA-upgrade recommendation (number matching → FIDO2).

## Pitfalls

- Uncapped push storms that harass users and generate helpdesk incidents — the cap is a
  safety control.
- Continuing after an approval to 'see how far it goes' — stop at the finding.
- Targeting users without a debrief plan; fatigue tests can erode trust if handled
  poorly.

## References

- MITRE ATT&CK: Multi-Factor Authentication Request Generation (T1621).
- CISA guidance on phishing-resistant MFA.

## Blue-team control under test

This playbook validates their identity monitoring and MFA policy are under test —
unalerted push storms and any approval are identity-program failures. Paired blue-team
counterpart: `cyber_core_mfa_fatigue`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
