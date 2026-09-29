---
skill_id: red_beacon_interval_analysis
name: Beacon Interval Analysis Test
description: Analyze beaconing intervals statistically to validate network-anomaly detection tuning.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, command-and-control, beaconing, analytics]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_command_and_control_beaconing
---
# Beacon Interval Analysis Test

## Purpose

Beaconing detection is statistics: interval regularity, jitter analysis, byte counts.
This test generates canary beacons with known profiles and validates that the network
analytics actually fire — tuning the detectors with ground truth.

## When to use

- As a detection-engineering exercise with the blue team.
- To tune beaconing analytics with labeled data.
- After HTTPS-C2 tests, as the analytics follow-on.

## Prerequisites

- Authorization for beacon generation; canary beacon infrastructure.
- NetOps/SOC coordination — this is a joint tuning exercise.

## Procedure

1. Generate canary beacons with known profiles: fixed interval, jittered, randomized, low-
   and-slow.
2. Feed the labeled beacon traffic to the analytics and record detection per profile.
3. Measure detection latency: how many beacons before the alert?
4. Test the evasion boundary: at what jitter/randomness does detection fail?
5. Deliver the beaconing-analytics tuning report with labeled datasets.

## Expected outputs

- Per-profile detection results with latency.
- Evasion-boundary measurements.
- Labeled beacon dataset for the SOC.

## Pitfalls

- Unlabeled beacon traffic confusing the SOC — label everything, coordinate timing.
- Beaconing from production hosts without approval — dedicated test hosts.

## References

- Network beaconing-detection literature (public).

## Blue-team control under test

This playbook validates their beaconing analytics get ground-truth tuning data — labeled
beacons are the detection-engineering gift. Paired blue-team counterpart:
`cyber_hunting_for_command_and_control_beaconing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
