---
skill_id: red_registry_run_keys
name: Registry Run Key Persistence Test
description: Test registry run-key persistence mechanisms to validate autostart monitoring and EDR coverage.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, registry, windows]
version: 1.0.0
team: red
tests_blue: cyber_core_registry_persistence
---
# Registry Run Key Persistence Test

## Purpose

Registry run keys are the oldest persistence trick on Windows and still effective.
Testing them validates autostart-entry monitoring (Sysmon Event 13, EDR) and the blue
team's ability to distinguish legitimate software autostarts from attacker persistence.

## When to use

- During persistence phases on Windows hosts.
- To validate Sysmon registry-event coverage and EDR autostart rules.
- As a baseline persistence test before exotic mechanisms.

## Prerequisites

- Authorization for persistence testing with defined dwell time and cleanup.
- Registry baseline of the target hosts to distinguish test entries.

## Procedure

1. Create run-key entries (HKCU/HKLM Run, RunOnce) pointing at an inert canary executable;
   log exact keys and values.
2. Reboot or log off/on the target as authorized and verify the canary executed (canary
   file timestamp).
3. Record the telemetry: Sysmon 13 registry events, EDR autostart alerts, and whether the
   value data was inspected.
4. Test variations: RunOnceEx, Wow6432Node redirection, and run-key-adjacent locations
   (AppInit_DLLs concepts where authorized).
5. Measure detection latency from creation to alert.
6. Remove all test entries at phase end and verify removal events fired.
7. Deliver the autostart-monitoring assessment with Sysmon config recommendations.

## Expected outputs

- Per-location creation/detection matrix.
- Persistence-verification evidence (canary execution).
- Cleanup verification with removal telemetry.

## Pitfalls

- Leaving run keys behind — cleanup is part of the test.
- Testing HKLM keys without authorization for the privilege level.
- Forgetting Wow6432Node — 32-bit views hide entries from naive checks.

## References

- MITRE ATT&CK: Boot or Logon Autostart Execution — Registry Run Keys (T1547.001).

## Blue-team control under test

This playbook validates their autostart monitoring (Sysmon 13, EDR) faces the most basic
persistence there is — silent run keys are a foundational visibility gap. Paired blue-
team counterpart:
`cyber_core_registry_persistence`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
