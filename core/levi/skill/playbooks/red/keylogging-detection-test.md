---
skill_id: red_keylogging_detection_test
name: Keylogging Detection Test
description: Test keylogging techniques to validate behavioral detection of input capture.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, keylogging, detection]
version: 1.0.0
team: red
tests_blue: cyber_building_detection_rule_with_splunk_spl
---
# Keylogging Detection Test

## Purpose

Keyloggers capture credentials at the source. This test deploys canary keyloggers — API
hooks, raw input, kernel concepts discussed-only — and validates whether behavioral
detection catches input-capture techniques.

## When to use

- During collection phases on Windows.
- To validate EDR behavioral rules for input-capture APIs.
- To test user-awareness: do users notice the canary keylogger's indicators?

## Prerequisites

- Authorization for input-capture testing on test hosts.
- Canary keystrokes only; captured data destroyed immediately.

## Procedure

1. Deploy a canary keylogger using SetWindowsHookEx on the test host; type canary
   credentials.
2. Test raw-input and GetAsyncKeyState polling variants.
3. Record per variant: EDR alert, API-monitoring events, and whether canary keystrokes were
   captured.
4. Verify the captured canary data, then destroy it and remove the keylogger.
5. Kernel keylogger concepts: discuss and validate driver-signing policy instead of
   deploying.
6. Deliver the input-capture detection assessment.

## Expected outputs

- Per-variant keylogger detection results.
- Canary-capture verification and destruction log.
- Driver-signing policy assessment.

## Pitfalls

- Capturing real user keystrokes — canary input sessions only, scheduled and supervised.
- Kernel keyloggers on real hardware — concepts and policy only.
- Leaving the keylogger installed — removal verified, not assumed.

## References

- MITRE ATT&CK: Input Capture — Keylogging (T1056.001).

## Blue-team control under test

This playbook validates their behavioral detection of input capture is under test —
silent keyloggers are a credential-theft gap. Paired blue-team counterpart:
`cyber_building_detection_rule_with_splunk_spl`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
