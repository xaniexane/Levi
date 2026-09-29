---
skill_id: red_defender_exclusion_abuse
name: Defender Exclusion Abuse Test
description: Test Microsoft Defender exclusion abuse to validate exclusion governance and monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, defender, exclusions]
version: 1.0.0
team: red
tests_blue: cyber_configuring_windows_defender_advanced_settings
---
# Defender Exclusion Abuse Test

## Purpose

Defender exclusions are a sanctioned blind spot — attackers with admin rights add
exclusions for their tooling. This test adds canary exclusions and validates whether
exclusion changes are monitored, alerted, and governed by policy.

## When to use

- During defense-evasion phases on Defender-managed hosts.
- To validate exclusion-change alerting (event 5007).
- To audit the existing exclusion list for overly broad entries.

## Prerequisites

- Authorization for Defender configuration changes on test hosts.
- Canary exclusions scoped to test paths only.

## Procedure

1. Audit the existing exclusion list for broad entries (entire drives, temp paths, process
   exclusions) — report these regardless.
2. Add a canary path exclusion via authorized tooling; record whether event 5007 fired and
   whether any alert reached the SOC.
3. Test exclusion via GPO/Intune vs. local — which paths does the blue team monitor?
4. Verify the canary path is actually unscanned (EICAR-style canary file, not real
   malware).
5. Remove all test exclusions; verify the exclusion list matches the pre-test baseline.
6. Deliver the exclusion-governance assessment with least-exclusion recommendations.

## Expected outputs

- Pre-existing exclusion audit with risk ratings.
- Exclusion-change detection timeline.
- Baseline-restoration verification.

## Pitfalls

- Broad exclusions left behind — diff the exclusion list before and after.
- Real malware in the excluded path — canary files only.
- Testing GPO-managed exclusions without the AD team's coordination.

## References

- MITRE ATT&CK: Impair Defenses — Disable or Modify Tools (T1562.001).
- Microsoft Defender event 5007 documentation.

## Blue-team control under test

This playbook validates their Defender exclusion governance is under test — unmonitored
exclusion changes are an attacker-controlled blind spot. Paired blue-team counterpart:
`cyber_configuring_windows_defender_advanced_settings`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
