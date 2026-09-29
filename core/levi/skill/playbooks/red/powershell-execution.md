---
skill_id: red_powershell_execution
name: PowerShell Execution Techniques
description: Test PowerShell execution paths — including constrained language mode and bypasses — to validate endpoint controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, powershell]
version: 1.0.0
team: red
tests_blue: cyber_core_powershell_abuse
---
# PowerShell Execution Techniques

## Purpose

PowerShell is the most abused legitimate tool on Windows. This playbook tests the full
spectrum: normal execution, encoded commands, constrained language mode, and its
bypasses — measuring what the EDR sees and blocks at each level.

## When to use

- During the execution phase on Windows hosts, after initial access.
- To validate PowerShell Constrained Language Mode deployment.
- To test EDR script-block logging and AMSI integration.

## Prerequisites

- Authorization for code execution on the target hosts; lab-test payloads first.
- Confirmation of which PowerShell versions and language modes are in the baseline.

## Procedure

1. Baseline: run standard PowerShell commands and record EDR/script-block-logging
   telemetry.
2. Test encoded commands (`-EncodedCommand`) and download cradles against network controls
   — inert payloads only.
3. Check the language mode (`$ExecutionContext.SessionState.LanguageMode`); if Constrained,
   test documented bypass paths in the lab first, then as authorized.
4. Test PowerShell 7 / pwsh side-by-side: does the EDR cover the cross-platform host
   equally?
5. Measure logging: Script Block Logging (event 4104), Module Logging, and transcription —
   which fired, which were missing?
6. Map every technique to the EDR/EDR-policy control that should have caught it.

## Expected outputs

- Per-technique execution and detection matrix.
- Script-block-logging coverage assessment (4104 presence/absence).
- Constrained Language Mode validation results.

## Pitfalls

- Running untested bypasses that crash hosts or trigger full incident response outside
  the window.
- Assuming PowerShell 7 inherits the Windows PowerShell logging config — verify
  separately.
- Forgetting transcription/log forwarding — local logs that never reach the SIEM don't
  count as detection.

## References

- MITRE ATT&CK: PowerShell (T1059.001).
- Microsoft: PowerShell logging guidance.

## Blue-team control under test

This playbook validates their PowerShell hardening (CLM, logging, AMSI) gets a
technique-by-technique scorecard — silent execution is an endpoint-logging gap. Paired
blue-team counterpart:
`cyber_core_powershell_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
