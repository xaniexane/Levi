---
skill_id: red_wmi_execution
name: WMI-Based Execution
description: Test WMI as an execution and lateral-movement primitive to validate process-creation monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, wmi, lateral-movement]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_lateral_movement_via_wmi
---
# WMI-Based Execution

## Purpose

WMI (`wmic`, `Invoke-WmiMethod`, DCOM) is a dual-use admin tool and a classic lateral-
movement primitive. Testing it validates that process-creation telemetry (Sysmon Event
1, EDR) catches WMI-spawned processes and that the blue team can distinguish admin use
from attacker use.

## When to use

- During execution/lateral-movement phases on Windows estates.
- To validate Sysmon/EDR coverage of WMI provider host activity.
- When the threat model includes living-off-the-land lateral movement.

## Prerequisites

- Authorization for remote WMI execution against the target hosts.
- Baseline of legitimate WMI admin usage so the test doesn't drown in noise.

## Procedure

1. Execute inert commands locally via WMI (`wmic process call create`) and record the
   resulting telemetry (Sysmon 1, Security 4688).
2. Test remote WMI execution via DCOM against an authorized target; vary the spawning
   parent (wmiprvse.exe) behaviors.
3. Test WMI event-subscription creation as a persistence-adjacent technique (see the
   persistence playbook).
4. Check whether the EDR distinguishes interactive admin WMI from scripted attacker WMI —
   or alerts on both equally.
5. Measure detection latency from execution to alert.
6. Deliver the WMI telemetry map: what fired, what was silent, and the recommended
   Sysmon/EDR rules.

## Expected outputs

- WMI execution telemetry matrix (local vs. remote).
- Detection-latency measurements.
- Recommended Sysmon/EDR rule refinements.

## Pitfalls

- WMI queries that hang against unreachable hosts — set timeouts to avoid test delays.
- Testing during production admin windows where legitimate WMI noise masks the test —
  coordinate timing.
- Forgetting DCOM lateral paths while only testing local WMI.

## References

- MITRE ATT&CK: WMI (T1047).

## Blue-team control under test

This playbook validates their process-creation monitoring is the control under test —
WMI-spawned processes that generate no alert are a telemetry gap. Paired blue-team
counterpart: `cyber_hunting_for_lateral_movement_via_wmi`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
