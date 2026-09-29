---
skill_id: red_psexec_lateral_execution
name: PsExec-Style Lateral Execution Test
description: Test PsExec-style service-based lateral execution to validate service-creation monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, lateral-movement, psexec]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_smb
---
# PsExec-Style Lateral Execution Test

## Purpose

PsExec-style execution (SMB + service creation) is the canonical lateral-movement
primitive. Testing it validates service-installation telemetry (Security 7045, Sysmon 1
with services.exe parent) and the blue team's ability to distinguish admin tooling from
attacker lateral movement.

## When to use

- During lateral-movement phases on Windows estates.
- To validate service-creation auditing and EDR lateral-movement rules.
- When the threat model includes credential-based lateral spread.

## Prerequisites

- Authorization for remote service creation; credentials obtained under authorization.
- Target list of hosts where lateral execution is permitted.

## Procedure

1. Execute an inert command on an authorized target via PsExec-style service creation (SMB
   admin share + service install).
2. Record the full telemetry: 7045 service-install events, the service binary path, and
   child-process ancestry.
3. Test variants: native PsExec, Impacket-style, WMI-based — each generates different
   telemetry the blue team must catch.
4. Measure detection latency and whether the EDR flagged the lateral movement specifically
   or just the process.
5. Clean up: remove the created services and verify removal events.
6. Map which variants were silent and recommend detection rules per variant.

## Expected outputs

- Per-variant execution and detection matrix.
- Service-cleanup verification.
- Detection-rule recommendations per lateral variant.

## Pitfalls

- Leaving services installed — cleanup is mandatory and verified.
- Using production admin credentials for the test — use dedicated test credentials.
- Testing against hosts outside the lateral-movement target list.

## References

- MITRE ATT&CK: Lateral Movement via service execution (T1569.002, T1021).

## Blue-team control under test

This playbook validates their service-installation monitoring (7045) and lateral-
movement detections face the canonical technique — silent PsExec is a high-severity
detection gap. Paired blue-team counterpart:
`cyber_core_lateral_movement_smb`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
