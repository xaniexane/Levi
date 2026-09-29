---
skill_id: red_recovery_time_drill
name: Recovery Time Drill
description: Drill full recovery timing to validate RTO/RPO claims against reality.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, impact, recovery, rto]
version: 1.0.0
team: red
tests_blue: cyber_testing_ransomware_recovery_procedures
---
# Recovery Time Drill

## Purpose

RTO/RPO numbers in the BCP are claims until drilled. This exercise times a full recovery
of canary systems from backups, producing the honest numbers leadership plans against.

## When to use

- As a resilience drill, independent of attack phases.
- To validate business-continuity plan recovery claims.
- After backup-restoration tests, at full-system scale.

## Prerequisites

- Canary systems and data; recovery-team participation.
- Agreed drill scope and success criteria.

## Procedure

1. Declare the drill: canary systems 'lost', recovery begins.
2. Time every phase: backup location, restoration, configuration, validation, handover.
3. Record gaps: missing credentials, undocumented steps, broken runbook links.
4. Compare measured RTO/RPO against the BCP claims.
5. Deliver the recovery-timing report with runbook fixes.

## Expected outputs

- Measured RTO/RPO per system.
- BCP-claim vs. reality deltas.
- Runbook gap list.

## Pitfalls

- Declaring success at 'data restored' — recovery means operational, validated, handed
  over.
- Drilling only the easy systems — include the hard ones.

## References

- NIST SP 800-34 (contingency planning).

## Blue-team control under test

This playbook validates their recovery claims get timed honestly — the delta between BCP
numbers and drill numbers is the finding. Paired blue-team counterpart:
`cyber_testing_ransomware_recovery_procedures`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
