---
skill_id: red_scheduled_task_execution
name: Scheduled Task Execution Test
description: Test scheduled tasks as an execution primitive to validate task-creation monitoring and alerting.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, scheduled-tasks]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_malware_persistence_with_autoruns
---
# Scheduled Task Execution Test

## Purpose

Scheduled tasks (`schtasks`, Task Scheduler COM) are a built-in execution primitive
abused for both one-shot execution and persistence. This test measures whether task
creation, modification, and execution generate the expected telemetry (Security
4698/4702, Sysmon 1 with taskeng parent).

## When to use

- During execution phases on Windows hosts.
- To validate scheduled-task auditing GPOs are actually applied.
- As a precursor to the persistence-phase task tests.

## Prerequisites

- Authorization for task creation on the targets; tasks must be uniquely named and time-
  bounded.
- Agreement on cleanup: every test task is deleted at phase end.

## Procedure

1. Create a one-shot scheduled task running an inert command (canary file write) via
   schtasks and via the COM API.
2. Record the telemetry: Security events 4698 (creation), 4702 (update), 4699 (deletion),
   and the child process ancestry.
3. Test tasks running as SYSTEM vs. as user — do the controls distinguish privilege levels?
4. Test task creation via remote RPC (atsvc) where in scope.
5. Verify cleanup: delete all test tasks and confirm deletion events fired.
6. Map gaps: which creation methods were silent, and which GPO settings close them.

## Expected outputs

- Task-creation telemetry matrix per creation method.
- Cleanup verification (all test tasks removed, deletion events logged).
- GPO hardening recommendations for task auditing.

## Pitfalls

- Leaving test tasks behind — the cleanup step is part of the test, not optional.
- Creating tasks as SYSTEM without explicit authorization for privilege level.
- Missing the COM-API creation path while only testing schtasks.exe.

## References

- MITRE ATT&CK: Scheduled Task (T1053.005).

## Blue-team control under test

This playbook validates their scheduled-task auditing (4698/4702) is the control under
test — silent task creation is an audit-policy gap. Paired blue-team counterpart:
`cyber_analyzing_malware_persistence_with_autoruns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
