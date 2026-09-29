---
skill_id: red_winrm_lateral_test
name: WinRM Lateral Movement Test
description: Test WinRM-based lateral movement to validate WinRM logging and JEA controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, winrm, powershell]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_powershell_script_block_logging
---
# WinRM Lateral Movement Test

## Purpose

WinRM is the modern admin remoting — PowerShell remoting rides it. This test validates
that WinRM operational logging captures remote commands, and that Just Enough
Administration constrains what remote sessions can do.

## When to use

- During lateral-movement phases.
- To validate PowerShell remoting logging (4103/4104, WinRM operational).
- To test JEA endpoint constraints.

## Prerequisites

- Authorization for WinRM remoting between the named hosts.
- Inert remote commands (canary).

## Procedure

1. Execute remote commands via WinRM/PowerShell remoting with the authorized credential;
   run canary commands.
2. Record telemetry: WinRM operational logs, PowerShell 4103/4104 script-block logging on
   the target.
3. Test JEA endpoints: what can the constrained session actually do? Attempt boundary
   escapes (authorized, proof-only).
4. Verify the canary executed; clean artifacts.
5. Deliver the WinRM-logging and JEA assessment.

## Expected outputs

- WinRM remoting telemetry record.
- JEA constraint test results.
- Script-block logging coverage findings.

## Pitfalls

- JEA escape attempts beyond proof-of-concept without approval.
- Assuming 4104 logging is on everywhere — verify per host.

## References

- MITRE ATT&CK: Remote Services — Windows Remote Management (T1021.006).
- Microsoft: JEA documentation.

## Blue-team control under test

This playbook validates their WinRM logging and JEA constraints are under test —
unconstrained remoting with silent script blocks is a double gap. Paired blue-team
counterpart: `cyber_analyzing_powershell_script_block_logging`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
