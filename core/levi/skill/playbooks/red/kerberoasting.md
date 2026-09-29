---
skill_id: red_kerberoasting
name: Kerberoasting Test
description: Test Kerberoasting (requesting crackable service tickets) to validate service-account password hygiene.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, kerberos, active-directory]
version: 1.0.0
team: red
tests_blue: cyber_core_kerberoasting
---
# Kerberoasting Test

## Purpose

Service accounts with weak passwords and SPNs hand attackers crackable Kerberos tickets
— no privileged access needed, just any domain user. This test requests service tickets,
extracts the hashes, and cracks them offline in the lab to prove which service accounts
fall.

## When to use

- During AD privilege-escalation phases with any domain user context.
- To validate service-account password policy and SPN hygiene.
- After user-hunting shows service accounts with old passwords.

## Prerequisites

- Authorization for the AD environment; any domain user context suffices for the request
  phase.
- Cracking performed offline in the lab — never on the target network.

## Procedure

1. Enumerate user accounts with SPNs set (service accounts) via LDAP.
2. Request TGS tickets for each SPN-holding account and extract the ticket hashes
   (Rubeus/Impacket-style, authorized tooling).
3. Transfer hashes to the lab and attempt offline cracking with the agreed wordlists/rules.
4. For each cracked account, verify the impact: what does this service account administer?
5. Record detection: did requesting dozens of TGS tickets trip any alert (Honeypot SPNs,
   unusual TGS volume)?
6. Deliver the crackable-service-account list with password-policy and managed-service-
   account recommendations.

## Expected outputs

- Service-account enumeration with SPN details.
- Crack results per account (lab only).
- Detection assessment for TGS-request anomalies.

## Pitfalls

- Cracking on the target network or with cloud GPUs outside the agreed lab — keep it in
  the lab.
- Using cracked service-account credentials beyond verification without fresh
  authorization.
- Forgetting AES-only enforcement as the mitigation — note it in recommendations.

## References

- MITRE ATT&CK: Steal or Forge Kerberos Tickets — Kerberoasting (T1558.003).

## Blue-team control under test

This playbook validates their service-account password hygiene is the finding — every
cracked account is a password-policy failure, and silent mass TGS requests are a
detection gap. Paired blue-team counterpart:
`cyber_core_kerberoasting`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
