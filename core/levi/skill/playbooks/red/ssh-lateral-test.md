---
skill_id: red_ssh_lateral_test
name: SSH Lateral Movement Test
description: Test SSH-based lateral movement to validate Linux authentication monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, ssh, linux]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_rdp
---
# SSH Lateral Movement Test

## Purpose

SSH is the Linux lateral-movement plane. This test moves between Linux hosts via SSH
with authorized keys and passwords, validating auth.log monitoring, key hygiene, and
whether lateral SSH is distinguishable from admin SSH.

## When to use

- During lateral-movement phases on Linux estates.
- To validate SSH authentication monitoring and alerting.
- To audit authorized_keys hygiene across hosts.

## Prerequisites

- Authorization for SSH movement between the named hosts.
- Test keys; canary commands.

## Procedure

1. Move between hosts via SSH with authorized test keys; run canary commands.
2. Test password auth where enabled (authorized) — record the difference in telemetry.
3. Audit authorized_keys files on the targets for stale/unknown keys.
4. Record telemetry: auth.log entries, SIEM SSH alerts, EDR process ancestry.
5. Test SSH agent forwarding abuse paths (authorized, proof-only) and note the risk.
6. Remove test keys; verify authorized_keys matches baseline.
7. Deliver the SSH-monitoring and key-hygiene assessment.

## Expected outputs

- SSH movement telemetry record.
- authorized_keys hygiene findings.
- Agent-forwarding risk notes.

## Pitfalls

- Leaving test keys in authorized_keys — verify removal per host.
- Agent forwarding with real keys — test keys only.
- Password-auth testing without approval where policy disables it.

## References

- MITRE ATT&CK: Remote Services — SSH (T1021.004).

## Blue-team control under test

This playbook validates their Linux authentication monitoring and key hygiene are under
test — stale authorized_keys are persistent access the blue team forgot. Paired blue-
team counterpart:
`cyber_core_lateral_movement_rdp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
