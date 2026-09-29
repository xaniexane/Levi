---
skill_id: red_screen_capture_ops_test
name: Screen Capture Operations Test
description: Test systematic screen capture to validate DLP and insider-threat monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, screen-capture, dlp]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Screen Capture Operations Test

## Purpose

Systematic screenshotting captures whatever the user sees — including credentials and
sensitive documents. This test runs canary screen-capture sessions and validates whether
DLP, EDR, or insider-threat tooling notices.

## When to use

- During collection phases, with explicit authorization.
- To validate insider-threat monitoring coverage.
- To test DLP's handling of image-based exfiltration.

## Prerequisites

- Explicit authorization for screen capture; canary desktop sessions only.
- User notification per the ROE.

## Procedure

1. Run a canary screen-capture session on the test host (time-boxed, canary desktop).
2. Record telemetry: EDR alerts on capture APIs, DLP image analysis, insider-threat
   tooling.
3. Test exfiltration of the screenshots via the authorized exfil channel (canary).
4. Verify all screenshots destroyed after analysis.
5. Deliver the screen-capture detection assessment.

## Expected outputs

- Capture-session detection results.
- Screenshot-exfiltration test results.
- Destruction verification.

## Pitfalls

- Capturing real user desktops — canary sessions only.
- Screenshots retained beyond the analysis — destroy per the ROE.

## References

- MITRE ATT&CK: Screen Capture (T1113).

## Blue-team control under test

This playbook validates their insider-threat and DLP image handling are under test —
silent systematic capture is the insider-monitoring gap. Paired blue-team counterpart:
`cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
