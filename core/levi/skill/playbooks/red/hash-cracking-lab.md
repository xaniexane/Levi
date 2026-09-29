---
skill_id: red_hash_cracking_lab
name: Offline Hash-Cracking Lab Test
description: Crack captured hashes offline in the lab to validate password-policy strength.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, credential-access, hash-cracking, lab]
version: 1.0.0
team: red
tests_blue: cyber_implementing_passwordless_authentication_with_fido2
---
# Offline Hash-Cracking Lab Test

## Purpose

Captured hashes are only as strong as the passwords behind them. This lab test cracks
authorized hash sets offline to produce the password-policy verdict: what fraction falls
to dictionary, rules, and brute force — and what that means for policy.

## When to use

- As a password-policy audit, using hashes obtained under authorization.
- After any credential-dumping phase that produced hashes.
- To justify policy changes (length, managers, MFA).

## Prerequisites

- Hashes obtained under explicit authorization; lab-only cracking.
- Cracking wordlists and rules agreed; results handled per the credential ROE.

## Procedure

1. Transfer authorized hashes to the isolated lab; verify chain of custody.
2. Crack in stages: dictionary, dictionary+rules, targeted masks, full brute force (time-
   boxed).
3. Record per-stage crack rates and the time-to-crack distribution.
4. Analyze patterns: seasons, company names, keyboard walks — the policy failures made
   visible.
5. Destroy the hashes and results per the ROE after reporting (retain statistics, not
   values).
6. Deliver the password-policy verdict with specific policy recommendations.

## Expected outputs

- Per-stage crack-rate statistics.
- Password-pattern analysis.
- Policy recommendations with evidence.
- Destruction log for hash material.

## Pitfalls

- Cracking outside the isolated lab — never on shared infrastructure.
- Retaining cracked passwords beyond the report — statistics outlive values.
- Presenting crack rates without the time-box context — methodology matters.

## References

- MITRE ATT&CK: Brute Force — Password Cracking (T1110.002).

## Blue-team control under test

This playbook validates their password policy gets an empirical verdict — crack-rate
statistics are the evidence that changes policy. Paired blue-team counterpart:
`cyber_implementing_passwordless_authentication_with_fido2`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
