---
skill_id: red_wiper_impact_test
name: Wiper Impact Validation Test
description: Validate wiper-style destruction impact in a lab to test recovery and resilience.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, impact, wiper, lab]
version: 1.0.0
team: red
tests_blue: cyber_testing_ransomware_recovery_procedures
---
# Wiper Impact Validation Test

## Purpose

Wipers don't ask for ransom — they destroy. This lab test simulates wiper-style
destruction against canary systems and validates the resilience story: what survives,
what rebuilds, how fast.

## When to use

- Lab-only, for destructive-impact readiness.
- To validate bare-metal recovery and rebuild runbooks.
- When the threat model includes nation-state actors.

## Prerequisites

- Isolated lab; explicit authorization for destructive testing.
- Rebuild-team participation.

## Procedure

1. Snapshot everything; prepare the rebuild runbook as the test subject.
2. Execute wiper-style destruction (MBR/partition concepts, file wiping) against canary lab
   systems.
3. Record EDR behavior during the destruction.
4. Execute the rebuild runbook: measure time to operational, data loss, and runbook gaps.
5. Test offline backups and gold images as the recovery path.
6. Deliver the wiper-readiness report.

## Expected outputs

- Destruction-vs-detection timeline.
- Rebuild measurements and runbook gaps.
- Offline-recovery findings.

## Pitfalls

- Lab escape — network-isolated, snapshot-backed, no exceptions.
- Real wiper samples — canary destruction routines.
- Skipping the rebuild — the rebuild IS the test.

## References

- MITRE ATT&CK: Data Destruction (T1485), Disk Wipe (T1561).

## Blue-team control under test

This playbook validates their destructive-attack resilience is drilled — rebuild time is
the metric that matters. Paired blue-team counterpart:
`cyber_testing_ransomware_recovery_procedures`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
