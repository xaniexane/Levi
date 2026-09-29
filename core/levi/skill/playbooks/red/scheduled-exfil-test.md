---
skill_id: red_scheduled_exfil_test
name: Scheduled Exfiltration Test
description: Test scheduled/low-and-slow exfiltration to validate anomaly detection over time.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, scheduling, anomaly]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Scheduled Exfiltration Test

## Purpose

Low-and-slow exfiltration — small amounts on a schedule — defeats volume thresholds.
This time-boxed test exfiltrates canary data on a schedule and validates whether time-
based anomaly detection notices the pattern.

## When to use

- During exfiltration phases, as the stealth variant.
- To validate UEBA time-series anomaly detection.
- To tune DLP away from pure volume thresholds.

## Prerequisites

- Authorization for exfiltration testing; canary data only; agreed schedule and total
  volume cap.
- Longer time-box agreed with the blue team.

## Procedure

1. Exfiltrate canary data in small scheduled batches within the agreed volume cap.
2. Vary the schedule: business-hours blending vs. off-hours.
3. Monitor detection daily: did time-series analytics flag the pattern? When?
4. Test the threshold boundary: find the batch size/frequency that stays silent (within the
   cap).
5. Verify all canary data destroyed at the destination.
6. Deliver the scheduled-exfiltration assessment with analytics-tuning recommendations.

## Expected outputs

- Detection timeline across the schedule.
- Threshold-boundary measurements (within cap).
- Time-series analytics findings.

## Pitfalls

- Exceeding the volume cap — the cap is the authorization.
- Running past the agreed time-box — schedule discipline.
- Real data in the trickle — canary only.

## References

- MITRE ATT&CK: Exfiltration — scheduled transfer literature.

## Blue-team control under test

This playbook validates their time-based anomaly detection is under test — silent
scheduled exfil within the cap is the analytics gap. Paired blue-team counterpart:
`cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
