---
skill_id: red_credential_manager_abuse
name: Credential Manager Abuse Test
description: Test Windows Credential Manager and DPAPI abuse to validate stored-credential protections.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, dpapi, credential-manager]
version: 1.0.0
team: red
tests_blue: cyber_abusing_dpapi_for_credential_access
---
# Credential Manager Abuse Test

## Purpose

Windows Credential Manager stores user credentials encrypted with DPAPI — decryptable in
the user's context. This test validates what an attacker with user-context access can
recover, and whether DPAPI-abuse tooling is detected.

## When to use

- During credential-access phases on user workstations.
- To validate the risk of credentials stored in Credential Manager and browsers.
- After gaining user-context access in an exercise.

## Prerequisites

- Authorization for the test user contexts; canary credentials planted for the test.
- Agreement on whether real stored credentials may be viewed (prefer canaries).

## Procedure

1. Plant canary credentials in the test users' Credential Manager vaults.
2. With user-context access, enumerate and decrypt the vaults using authorized tooling;
   record success.
3. Test DPAPI master-key paths: with and without the user's password context.
4. Record EDR telemetry during vault enumeration and DPAPI abuse.
5. Audit real vaults (with approval) for high-value stored credentials — report counts, not
   values.
6. Remove canary credentials; verify vaults are clean.

## Expected outputs

- Vault-recovery feasibility per context.
- DPAPI-abuse detection results.
- Stored-credential hygiene findings (counts).

## Pitfalls

- Reading users' real stored passwords without explicit approval — canaries first.
- Exporting vault contents off the host — analyze in place, report counts.
- Forgetting browser-stored credentials in the same audit — include them.

## References

- MITRE ATT&CK: Credentials from Password Stores (T1555).

## Blue-team control under test

This playbook validates their stored-credential hygiene is under test — every production
password recoverable from a vault is a credential-storage finding. Paired blue-team
counterpart: `cyber_abusing_dpapi_for_credential_access`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
