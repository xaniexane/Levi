---
skill_id: red_wmi_lateral_test
name: WMI Lateral Movement Test
description: Test WMI-based lateral movement to validate DCOM and WMI operational-log monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, wmi, dcom]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_dcom_lateral_movement
---
# WMI Lateral Movement Test

## Purpose

WMI lateral movement rides DCOM — no service installation, different telemetry than
PsExec. This test validates that WMI operational logs and DCOM monitoring catch remote
process creation via Win32_Process.

## When to use

- During lateral-movement phases.
- To validate WMI operational-log forwarding from all hosts.
- To compare against the PsExec baseline (different telemetry, different gaps).

## Prerequisites

- Authorization for lateral movement between the named hosts.
- Inert remote payload (canary).

## Procedure

1. Execute remote process creation via WMI (Win32_Process.Create) on the target with the
   authorized credential.
2. Record telemetry: WMI operational log events, DCOM 10036-style events, 4624 logons, EDR
   process-ancestry.
3. Test from non-standard initiators to check ancestry rules.
4. Verify the canary executed; clean all artifacts.
5. Compare detection against the PsExec baseline — which layers fired differently?
6. Deliver the WMI-movement assessment with operational-log recommendations.

## Expected outputs

- WMI lateral-movement telemetry record.
- PsExec-vs-WMI detection comparison.
- Operational-log coverage findings.

## Pitfalls

- Assuming the WMI operational log is forwarded everywhere — verify per host.
- Lateral movement outside the named hosts.

## References

- MITRE ATT&CK: Windows Management Instrumentation for lateral movement (T1047).

## Blue-team control under test

This playbook validates their WMI/DCOM monitoring is measured against the PsExec floor —
gaps here are operational-log forwarding failures. Paired blue-team counterpart:
`cyber_hunting_for_dcom_lateral_movement`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
