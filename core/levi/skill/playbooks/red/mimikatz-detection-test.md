---
skill_id: red_mimikatz_detection_test
name: Mimikatz and Credential Tooling Detection Test
description: Test signatured credential-dumping tools to validate AV/EDR signature and behavioral coverage.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, mimikatz, detection]
version: 1.0.0
team: red
tests_blue: cyber_detecting_mimikatz_execution_patterns
---
# Mimikatz and Credential Tooling Detection Test

## Purpose

Mimikatz is the most signatured tool in existence — if it runs silently, signature and
behavioral layers are both failing. This controlled test executes renamed, obfuscated,
and in-memory variants to score each layer honestly.

## When to use

- During credential-access phases.
- To validate the signature-to-behavioral detection spectrum.
- As a canary for AV/EDR health: it should NEVER run silent.

## Prerequisites

- Authorization for credential-tooling on test hosts.
- Inert execution goals: sekurlsa::logonpasswords output to canary verification only
  where explicitly authorized; otherwise load-and-detect tests.

## Procedure

1. Baseline: run the stock binary — record block/alert.
2. Run renamed, recompiled, and in-memory (reflective-load) variants — record per-variant
   outcomes.
3. Run the PowerShell and .NET in-memory variants — record AMSI + behavioral outcomes.
4. Score each variant: blocked pre-execution, alerted on behavior, or silent.
5. Verify no credential material persists on the test host after the exercise.
6. Deliver the signature-vs-behavioral scorecard.

## Expected outputs

- Per-variant detection outcomes (stock → in-memory).
- Signature-vs-behavioral layering analysis.
- Cleanup verification.

## Pitfalls

- Real credential output captured without approval — scope the extraction goal first.
- Variants that the EDR quarantines the test tooling over — coordinate with the SOC.
- Concluding 'detected' from a signature alone — the in-memory variants test the
  behavioral layer.

## References

- MITRE ATT&CK: OS Credential Dumping (T1003).

## Blue-team control under test

This playbook validates their AV/EDR layering gets a brutally honest scorecard — a
silent Mimikatz variant is a layered-detection failure. Paired blue-team counterpart:
`cyber_detecting_mimikatz_execution_patterns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
