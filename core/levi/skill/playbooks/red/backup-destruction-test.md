---
skill_id: red_backup_destruction_test
name: Backup Destruction Test
description: Test backup-target attacks to validate backup immutability and isolation.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, impact, backups, ransomware]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_ransomware_encryption_mechanisms
---
# Backup Destruction Test

## Purpose

Modern ransomware kills the backups first. This test attacks canary backup targets with
the compromised-context credentials, validating immutability, air-gapping, and whether
backup deletion alerts anyone.

## When to use

- During impact phases, against canary backup targets.
- To validate backup immutability (object lock, air gap).
- Paired with the ransomware-impact lab test.

## Prerequisites

- Authorization for backup-target testing; canary backup data.
- Backup-team participation — this is their control being tested.

## Procedure

1. From the compromised test context, attempt backup deletion, encryption, and retention-
   policy changes.
2. Test immutability: does object lock / air gap actually stop the deletion?
3. Record alerting: did backup-tampering generate any alert, and how fast?
4. Test the backup-console: can the attacker pivot through the backup software itself?
5. Verify canary backups intact afterward; restore one as proof.
6. Deliver the backup-resilience report.

## Expected outputs

- Backup-attack results per technique.
- Immutability-verification evidence.
- Backup-tampering alert timeline.

## Pitfalls

- Production backup targets — canary targets only.
- Actually deleting backups even as a test — immutability should stop you; verify, don't
  force.

## References

- MITRE ATT&CK: Inhibit System Recovery (T1490).

## Blue-team control under test

This playbook validates their backup strategy faces the attack it's designed for —
deletable backups are the finding that matters most. Paired blue-team counterpart:
`cyber_analyzing_ransomware_encryption_mechanisms`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
