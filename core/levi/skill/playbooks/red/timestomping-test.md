---
skill_id: red_timestomping_test
name: Timestomping Detection Test
description: Test timestomping (timestamp manipulation) to validate forensic timeline integrity controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, timestomping, forensics]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_defense_evasion_via_timestomping
---
# Timestomping Detection Test

## Purpose

Timestomping rewrites file timestamps to corrupt forensic timelines. This test
timestomps canary files and validates whether the blue team's forensic tooling and
timeline analysis detect the manipulation (USN journal, $STANDARD_INFORMATION vs.
$FILE_NAME discrepancies).

## When to use

- During defense-evasion phases.
- To validate forensic readiness: can the team detect timeline tampering?
- As a DFIR exercise input — the timestomped files become the investigation scenario.

## Prerequisites

- Authorization for the test hosts; canary files in a test directory.
- DFIR team awareness if the test doubles as an exercise.

## Procedure

1. Create canary files, then timestomp their MFT timestamps (creation/modification) to
   misleading values.
2. Have the blue/DFIR side analyze: do their tools flag the $SI/$FN discrepancy? Does the
   USN journal contradict the timestamps?
3. Record which forensic tools detected the tampering and which trusted the forged
   timestamps.
4. Test timestomping on executables placed in autostart locations (combined persistence +
   evasion).
5. Restore or delete all canary files; verify the test directory is clean.
6. Deliver the forensic-timeline-integrity assessment.

## Expected outputs

- Per-tool timestomp-detection results.
- USN/MFT discrepancy evidence.
- DFIR exercise debrief (if combined).

## Pitfalls

- Timestomping outside the test directory — scope strictly.
- Forgetting the USN journal also needs checking — that's the detection path.
- Presenting timestomping as unstoppable — the discrepancies ARE detectable with the
  right analysis.

## References

- MITRE ATT&CK: Indicator Removal — Timestomp (T1070.006).

## Blue-team control under test

This playbook validates their forensic timeline discipline is under test — teams that
trust $STANDARD_INFORMATION blindly will misdate the whole intrusion. Paired blue-team
counterpart: `cyber_hunting_for_defense_evasion_via_timestomping`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
