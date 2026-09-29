---
skill_id: red_rdp_lateral_test
name: RDP Lateral Movement Test
description: Test RDP-based lateral movement to validate RDP monitoring and session controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, rdp]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_rdp
---
# RDP Lateral Movement Test

## Purpose

RDP is legitimate admin tooling, which makes it ideal cover for lateral movement. This
test performs authorized RDP sessions between hosts and validates that RDP logons are
monitored, that session hosts are hardened, and that anomalous RDP is distinguishable.

## When to use

- During lateral-movement phases.
- To validate RDP logon monitoring (4624 type 10) and session-host hardening.
- To test whether RDP from unusual sources alerts.

## Prerequisites

- Authorization for RDP between the named hosts; test accounts.
- RDP session recording/consent per the ROE.

## Procedure

1. Establish RDP sessions from authorized sources to target hosts; perform canary actions.
2. Record telemetry: 4624 type 10, RDP session events, EDR logon alerts.
3. Test from an unusual source (as authorized) to check anomaly alerting.
4. Verify NLA, session timeouts, and clipboard/drive-redirection policies on the targets.
5. Close all sessions; verify no disconnected sessions remain.
6. Deliver the RDP-monitoring and hardening assessment.

## Expected outputs

- RDP telemetry record per session.
- Anomaly-detection test results.
- Session-host hardening findings.

## Pitfalls

- Leaving disconnected RDP sessions — verify clean logoff.
- Drive/clipboard redirection moving test artifacts unexpectedly — check policies first.
- RDP to sensitive hosts without specific approval.

## References

- MITRE ATT&CK: Remote Services — Remote Desktop Protocol (T1021.001).

## Blue-team control under test

This playbook validates their RDP monitoring and session-host hardening are under test —
unalerted anomalous RDP is a monitoring gap. Paired blue-team counterpart:
`cyber_core_lateral_movement_rdp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
