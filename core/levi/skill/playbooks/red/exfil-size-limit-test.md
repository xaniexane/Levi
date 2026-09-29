---
skill_id: red_exfil_size_limit_test
name: Exfiltration Size-Limit Test
description: Test DLP size thresholds and archive nesting to validate inspection completeness.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, dlp, archives]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Exfiltration Size-Limit Test

## Purpose

DLP often skips large files, deep archives, and encrypted blobs — the exact containers
exfiltration uses. This test probes those boundaries with canary data to map what the
DLP actually inspects.

## When to use

- During exfiltration phases.
- To validate DLP inspection limits (size, depth, encryption).
- To tune DLP policies with boundary evidence.

## Prerequisites

- Authorization for exfiltration testing; canary data only.
- DLP-team coordination.

## Procedure

1. Exfiltrate canary data in files of increasing size; find the size threshold where
   inspection stops.
2. Test archive nesting: canary data nested 5, 10, 20 deep — where does extraction stop?
3. Test encrypted archives: does the DLP block, allow, or quarantine what it can't read?
4. Test split archives and renamed extensions.
5. Deliver the DLP-boundary map with policy recommendations.

## Expected outputs

- Size-threshold measurements.
- Archive-depth boundary results.
- Encrypted-container policy findings.

## Pitfalls

- Real data in the test archives — canary only.
- Crashing the DLP with pathological nesting — stay within sane bounds, coordinate.

## References

- DLP vendor documentation on inspection limits; MITRE T1027.

## Blue-team control under test

This playbook validates their DLP's inspection boundaries are mapped — every skipped
container type is a policy decision to make explicitly. Paired blue-team counterpart:
`cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
