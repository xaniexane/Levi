---
skill_id: red_dcsync_test
name: DCSync Test
description: Test DCSync credential replication to validate replication monitoring and privileged-account hygiene.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, active-directory, dcsync]
version: 1.0.0
team: red
tests_blue: cyber_core_dcsync_attack
---
# DCSync Test

## Purpose

DCSync abuses replication privileges to pull password hashes — including KRBTGT —
without touching the DC's disk. Testing it validates that replication rights are tightly
held and that the resulting 4662/5136-style replication telemetry actually alerts.

## When to use

- During AD privilege-escalation phases with elevated rights.
- To validate who holds replication privileges (the keys to the kingdom list).
- To test SIEM rules for anomalous replication traffic.

## Prerequisites

- High-privilege context obtained under authorization; explicit approval for hash
  retrieval.
- Strict credential-handling: retrieved hashes go to the lab, never linger.

## Procedure

1. Enumerate who holds DS-Replication-Get-Changes rights (the DCSync-capable principals).
2. With the authorized elevated context, perform a DCSync for a canary account first —
   prove the path with minimal data.
3. Record the replication telemetry: event 4662 access, network replication traffic, and
   SIEM alerts.
4. Test detection of DCSync from a non-DC host (the anomaly) vs. normal DC-to-DC
   replication.
5. Deliver the replication-rights inventory with least-privilege recommendations.
6. Verify credential hygiene: all retrieved material handled per the ROE and destroyed
   after the lab analysis.

## Expected outputs

- DCSync-capable principal inventory.
- Replication telemetry assessment (canary-first).
- Credential-handling and destruction log.

## Pitfalls

- DCSyncing KRBTGT or the full domain without explicit approval — canary accounts first,
  scope the rest.
- Leaving retrieved hashes on test systems — destroy per the ROE.
- Confusing normal replication with DCSync — the test is about non-DC initiators.

## References

- MITRE ATT&CK: OS Credential Dumping — DCSync (T1003.006).

## Blue-team control under test

This playbook validates their replication-privilege hygiene and 4662 monitoring are
under test — DCSync from a workstation that nobody noticed is a critical detection
failure. Paired blue-team counterpart:
`cyber_core_dcsync_attack`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
