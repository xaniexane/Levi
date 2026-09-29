---
skill_id: red_amsi_bypass_test
name: AMSI Bypass Validation Test
description: Test AMSI bypass techniques to validate that defenses do not depend on AMSI alone.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, amsi]
version: 1.0.0
team: red
tests_blue: cyber_deobfuscating_powershell_obfuscated_malware
---
# AMSI Bypass Validation Test

## Purpose

AMSI is a scan interface, not a security boundary — bypasses are public and reliable.
This test runs known AMSI bypass variants against the EDR stack to prove whether
detection survives AMSI failure, and to justify defense-in-depth beyond the scan
interface.

## When to use

- During defense-evasion phases on Windows.
- To validate that EDR detections don't collapse when AMSI is bypassed.
- To justify behavioral-over-signature detection investments.

## Prerequisites

- Authorization for in-memory bypass techniques on test hosts.
- Inert payloads only — the bypass delivers a canary, never a real payload.

## Procedure

1. Establish the AMSI baseline: confirm a known-bad canary string is blocked by AMSI on the
   test host.
2. Execute public AMSI bypass variants (field-tamper, DLL-hijack-free memory patch,
   obfuscated invocation) each delivering an inert canary.
3. For each variant, record: did AMSI fire, did the EDR's behavioral engine fire, did
   anything fire at all?
4. Measure per-variant detection outcome: blocked, alerted-only, or silent.
5. Re-test after any EDR tuning to confirm the bypass is still caught behaviorally (or
   document the residual gap).
6. Deliver the AMSI-dependence assessment: which detections survive AMSI failure.

## Expected outputs

- Per-variant AMSI/EDR outcome matrix.
- AMSI-dependence rating per detection control.
- Residual-gap documentation where behavioral coverage is missing.

## Pitfalls

- Real payloads behind the bypass — canaries only.
- Testing on production workstations without isolation — use test hosts.
- Treating a bypass as 'EDR evaded' when the behavioral engine still caught the canary —
  record both layers.

## References

- MITRE ATT&CK: Impair Defenses — Disable or Modify Tools (T1562.001).

## Blue-team control under test

This playbook validates their detection stack's dependence on AMSI is what's measured —
controls that die with AMSI are signature-dependent and need behavioral backup. Paired
blue-team counterpart: `cyber_deobfuscating_powershell_obfuscated_malware`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
