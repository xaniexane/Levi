---
skill_id: red_asrep_roasting
name: AS-REP Roasting Test
description: Test AS-REP roasting against accounts without Kerberos pre-authentication to validate account hardening.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, kerberos, active-directory]
version: 1.0.0
team: red
tests_blue: cyber_core_asreproasting
---
# AS-REP Roasting Test

## Purpose

Accounts with Kerberos pre-authentication disabled hand out crackable AS-REP hashes to
anyone who asks — no credentials needed. This test finds such accounts, grabs the
hashes, and cracks them offline to prove the exposure.

## When to use

- During AD privilege-escalation phases, even with zero credentials.
- To validate that pre-authentication is enforced on all accounts.

## Prerequisites

- Authorization for the AD environment; the request phase needs no credentials by
  design.
- Offline cracking in the lab only.

## Procedure

1. Enumerate accounts with DONT_REQUIRE_PREAUTH set via LDAP.
2. Request AS-REP hashes for each such account (no authentication required).
3. Crack the hashes offline in the lab with agreed wordlists.
4. For cracked accounts, assess impact and verify per the credential-handling ROE.
5. Check detection: are pre-auth-disabled accounts alerted on, and did the hash requests
   trip anything?
6. Deliver findings with the one-line fix per account (enable pre-authentication) and a
   sweep for reoccurrence.

## Expected outputs

- Pre-auth-disabled account list with evidence.
- Crack results (lab).
- Remediation verification (re-sweep after enabling pre-auth).

## Pitfalls

- Assuming only user accounts matter — service and legacy accounts get this flag too.
- Cracking outside the lab or keeping cracked passwords beyond the rotation workflow.

## References

- MITRE ATT&CK: Steal or Forge Kerberos Tickets — AS-REP Roasting (T1558.004).

## Blue-team control under test

This playbook validates their account-hardening baseline should have zero pre-auth-
disabled accounts — each one is a one-line fix, and the sweep is automatable. Paired
blue-team counterpart:
`cyber_core_asreproasting`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
