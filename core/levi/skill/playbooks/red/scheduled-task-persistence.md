---
skill_id: red_scheduled_task_persistence
name: Scheduled Task Persistence Test
description: Test scheduled-task persistence with hidden and SYSTEM-level tasks to validate task auditing.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, scheduled-tasks]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_malware_persistence_with_autoruns
---
# Scheduled Task Persistence Test

## Purpose

Scheduled tasks double as execution and persistence. This test creates tasks designed to
persist — hidden, SYSTEM-level, with triggers on idle/logon — and measures whether task
auditing (4698/4702) and EDR catch them, including the stealthier variants.

## When to use

- During persistence phases, after basic execution tests pass.
- To validate that scheduled-task auditing covers hidden and privileged tasks.

## Prerequisites

- Authorization for persistence with dwell time and cleanup defined.
- Task names uniquely identifying the test (e.g., prefix with the exercise codename).

## Procedure

1. Create persistence tasks: daily trigger, on-logon trigger, and on-idle trigger, each
   running an inert canary.
2. Test the hidden attribute and SYSTEM principal variants where authorized.
3. Verify persistence across reboot and user logon/logoff cycles.
4. Record telemetry per variant: 4698/4702 events, EDR alerts, and whether hidden tasks
   were surfaced in audits.
5. Test task modification (changing the action post-creation) and record 4702 update
   events.
6. Delete all test tasks; verify 4699 deletion events and that no artifacts remain.

## Expected outputs

- Per-variant persistence/detection matrix.
- Reboot/logon verification evidence.
- Cleanup verification.

## Pitfalls

- Hidden tasks forgotten at cleanup — enumerate tasks programmatically at phase end.
- SYSTEM-level tasks without explicit privilege authorization.
- Trigger conditions that fire during business hours and confuse users — schedule off-
  hours.

## References

- MITRE ATT&CK: Scheduled Task (T1053.005).

## Blue-team control under test

This playbook validates their task-auditing GPOs face stealthy variants here — hidden or
SYSTEM tasks that go unlogged are audit-policy failures. Paired blue-team counterpart:
`cyber_analyzing_malware_persistence_with_autoruns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
