---
skill_id: red_living_off_land_detection
name: Living-off-the-Land Detection Test
description: Test LOLBin abuse patterns to validate behavioral detection of legitimate-tool misuse.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, lolbin, behavioral]
version: 1.0.0
team: red
tests_blue: cyber_core_lolbins_abuse
---
# Living-off-the-Land Detection Test

## Purpose

LOLBins are signed, legitimate, and everywhere — detection must be behavioral (parent-
child anomalies, command-line patterns), not reputation-based. This test exercises
LOLBin abuse patterns with inert actions to score the behavioral rules.

## When to use

- During defense-evasion phases, after the execution-lab baseline.
- To validate Sysmon command-line logging and EDR behavioral rules.
- To tune LOLBin alerting without drowning the SOC in false positives.

## Prerequisites

- Authorization for the test hosts; inert LOLBin actions (canary file writes, no exfil).
- Command-line logging enabled as a prerequisite check.

## Procedure

1. Execute a battery of LOLBin abuse patterns with inert outcomes: mshta/jscript canary,
   rundll32 javascript canary, certutil download of a canary file, bitsadmin canary
   transfer.
2. For each pattern, record: command-line logged, EDR alert, parent-child anomaly flagged.
3. Test the benign baseline too: normal admin use of the same binaries — measure the false-
   positive distance.
4. Tune recommendations: which patterns alert reliably, which need new rules, which are too
   noisy to alert on.
5. Clean all canary artifacts.
6. Deliver the LOLBin behavioral scorecard.

## Expected outputs

- Per-pattern detection results (logged/alerted/silent).
- Benign-baseline comparison for tuning.
- Rule recommendations with noise estimates.

## Pitfalls

- LOLBin actions with real exfil or download of untrusted content — canary files only.
- No benign baseline — without it you can't tune without noise.
- Alerting on the binary name alone — that's the false-positive trap this test exposes.

## References

- MITRE ATT&CK: System Binary Proxy Execution (T1218); LOLBAS project (public).

## Blue-team control under test

This playbook validates their behavioral rules for legitimate-tool abuse are under test
— binary-name alerting is the false-positive trap this exercise exposes. Paired blue-
team counterpart:
`cyber_core_lolbins_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
