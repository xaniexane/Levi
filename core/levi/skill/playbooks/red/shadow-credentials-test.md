---
skill_id: red_shadow_credentials_test
name: Shadow Credentials Test
description: Test shadow-credential attacks (msDS-KeyCredentialLink) to validate privileged-attribute monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, active-directory, shadow-credentials]
version: 1.0.0
team: red
tests_blue: cyber_abusing_shadow_credentials_for_privesc
---
# Shadow Credentials Test

## Purpose

Shadow credentials abuse the msDS-KeyCredentialLink attribute: with write access to a
target's attribute, an attacker adds their own key and authenticates as the victim via
PKINIT — no password needed. Testing it validates attribute-write monitoring and AD
hardening.

## When to use

- During AD privilege-escalation phases.
- To validate monitoring of KeyCredentialLink modifications.
- When the environment uses Windows Hello for Business (the legitimate feature this
  abuses).

## Prerequisites

- Authorization for the AD environment; attribute-write rights obtained under
  authorization.
- Lab-preferred; production only with explicit approval.

## Procedure

1. Identify targets where the test principal holds write access to msDS-KeyCredentialLink
   (often via GenericWrite).
2. Add a canary key credential to a test target's link attribute using authorized tooling.
3. Authenticate as the target via PKINIT with the canary key — proof only.
4. Record telemetry: directory-service audit events for the attribute write and the PKINIT
   logon.
5. Remove the canary key credential; verify the attribute is clean.
6. Deliver findings with monitoring recommendations for KeyCredentialLink writes.

## Expected outputs

- Shadow-credential feasibility per target with evidence.
- Attribute-write telemetry assessment.
- Cleanup verification.

## Pitfalls

- Leaving key credentials on real accounts — verify removal on every target.
- Testing against privileged targets (Domain Admins) without specific approval.
- Confusing legitimate WHfB key material with test artifacts — label everything.

## References

- MITRE ATT&CK: account-manipulation via key credentials; public shadow-credentials
  research.

## Blue-team control under test

This playbook validates their directory auditing for KeyCredentialLink writes is under
test — silent attribute writes are an AD-monitoring gap. Paired blue-team counterpart:
`cyber_abusing_shadow_credentials_for_privesc`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
