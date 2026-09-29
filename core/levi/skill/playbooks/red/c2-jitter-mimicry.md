---
skill_id: red_c2_jitter_mimicry
name: C2 Jitter and Mimicry Test
description: Test C2 traffic mimicry (legitimate-service profiles) to validate anomaly detection.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, mimicry, c2]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_command_and_control_communication
---
# C2 Jitter and Mimicry Test

## Purpose

Advanced C2 mimics legitimate traffic — cloud APIs, social media, messaging platforms.
This test runs canary C2 over legitimate-service profiles and validates whether anomaly
detection distinguishes the mimicry from real use.

## When to use

- During advanced C2 phases.
- To validate UEBA/anomaly-detection tuning.
- To test allowlisted-domain monitoring (the trusted-domain blind spot).

## Prerequisites

- Authorization for C2 testing; canary infrastructure.
- Baseline of legitimate traffic for the mimicked services.

## Procedure

1. Profile legitimate traffic for the target service (timing, volume, endpoints).
2. Run canary C2 mimicking the profile; measure the statistical distance.
3. Check detection: did UEBA flag the anomalous use of a legitimate service?
4. Test data-volume anomalies: mimicry that moves 10x the normal volume.
5. Tear down; deliver the mimicry-detection assessment.

## Expected outputs

- Mimicry-vs-legitimate statistical comparison.
- UEBA detection results.
- Allowlisted-domain monitoring findings.

## Pitfalls

- Real user accounts on the mimicked services — canary accounts only.
- Mimicry volumes that impact the real service — rate-limit.

## References

- MITRE ATT&CK: Application Layer Protocol — C2 mimicry literature.

## Blue-team control under test

This playbook validates their anomaly detection faces its hardest case — mimicry it
can't distinguish is the UEBA-tuning gap. Paired blue-team counterpart:
`cyber_analyzing_command_and_control_communication`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
