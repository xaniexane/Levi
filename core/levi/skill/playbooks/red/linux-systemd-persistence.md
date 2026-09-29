---
skill_id: red_linux_systemd_persistence
name: Linux systemd Persistence Test
description: Test systemd service and timer persistence on Linux hosts to validate Linux autostart monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, linux, systemd]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_persistence_mechanisms_in_linux
---
# Linux systemd Persistence Test

## Purpose

On modern Linux, persistence means systemd: services, timers, and user units. This test
validates that Linux hosts have the equivalent of Windows autostart monitoring — unit-
file integrity checks, timer auditing, and EDR coverage of systemd-spawned processes.

## When to use

- During persistence phases on Linux estates.
- To validate that Linux hardening baselines cover systemd persistence.
- When the threat model includes Linux servers and cloud VMs.

## Prerequisites

- Authorization for the Linux hosts; root-level persistence needs explicit privilege
  approval.
- Inert unit payloads (canary file writes).

## Procedure

1. Create a systemd service unit and a timer unit running an inert canary; enable them.
2. Test user-level units (~/.config/systemd/user) vs. system units — different visibility,
   different controls.
3. Verify persistence across reboots and timer firings.
4. Record telemetry: auditd unit-file watches, EDR alerts, and journal entries.
5. Check for monitoring of the unit directories (/etc/systemd/system, user paths) via FIM
   or auditd.
6. Remove all units, reload the daemon, and verify clean state.

## Expected outputs

- Per-unit-type persistence/detection matrix.
- Reboot/timer verification evidence.
- Cleanup verification.

## Pitfalls

- System units without root authorization — match the privilege to the approval.
- Timer units with aggressive schedules creating noise — use sparse schedules.
- Forgetting user units, which survive in user sessions and are less monitored.

## References

- MITRE ATT&CK: Systemd Service (T1543.002).

## Blue-team control under test

This playbook validates their Linux monitoring often lags Windows — silent systemd
persistence is the finding that justifies Linux EDR and auditd baselines. Paired blue-
team counterpart: `cyber_analyzing_persistence_mechanisms_in_linux`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
