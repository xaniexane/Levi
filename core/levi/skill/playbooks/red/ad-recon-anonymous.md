---
skill_id: red_ad_recon_anonymous
name: Anonymous Active Directory Recon
description: Enumerate Active Directory anonymously (null sessions, LDAP binds) to measure what an unauthenticated attacker can learn.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, active-directory]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_active_directory_acl_abuse
---
# Anonymous Active Directory Recon

## Purpose

Measure exactly how much AD intelligence an unauthenticated attacker can gather: null-
session shares, anonymous LDAP binds, and unauthenticated RPC endpoints. The less
available anonymously, the harder the attacker's first step. Every anonymous disclosure
is a hardening finding.

## When to use

- Early in internal assessments, before credentialed access is obtained.
- To validate that anonymous LDAP binds and null sessions are disabled as policy
  requires.
- As a baseline: re-run after hardening to prove the disclosures are gone.

## Prerequisites

- Authorization for the AD environment; anonymous techniques only in this phase.
- Agreement that any credentials discovered will be reported, not used, until the
  credentialed phase is authorized.

## Procedure

1. Test null-session access to IPC$ and enumerate accessible shares with smbclient-style
   tooling.
2. Attempt anonymous LDAP binds and enumerate the naming contexts, then pull user/computer
   objects where allowed.
3. Query unauthenticated RPC endpoints (epmapper) for exposed interfaces.
4. Enumerate domain password policy, lockout policy, and Kerberos policy via anonymous-
   accessible attributes.
5. Document every object and attribute readable without credentials, with the exact query
   used.
6. Report the anonymous disclosure inventory to the blue team as hardening findings before
   proceeding to credentialed phases.

## Expected outputs

- Anonymous disclosure inventory: shares, LDAP objects, policies readable without auth.
- Exact queries/commands used, for blue-team reproduction.
- Hardening recommendations per disclosure (GPO settings to change).

## Pitfalls

- Using any discovered credential in this phase — report it and wait for the
  credentialed phase.
- Assuming 'anonymous bind failed' means secure — verify with multiple tools; some
  servers fail binds but still leak via other endpoints.
- Overlooking IPv6 LDAP and alternate DCs — test all domain controllers in scope.

## References

- MITRE ATT&CK: Permission Groups Discovery (T1069), Account Discovery (T1087).
- Microsoft: hardening LDAP signing and channel binding guidance.

## Blue-team control under test

This playbook validates their AD hardening baseline should make this inventory nearly
empty — every entry is a GPO or configuration fix with a known remediation. Paired blue-
team counterpart: `cyber_analyzing_active_directory_acl_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
