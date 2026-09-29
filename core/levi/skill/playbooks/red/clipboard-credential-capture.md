---
skill_id: red_clipboard_credential_capture
name: Clipboard Credential Capture Test
description: Test clipboard monitoring for credential exposure to validate user-awareness controls.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, credential-access, clipboard, awareness]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Clipboard Credential Capture Test

## Purpose

Credentials live on clipboards constantly — copied passwords, tokens, connection
strings. This test measures clipboard credential exposure in the environment and
validates user-awareness training and clipboard-manager policies.

## When to use

- During credential-access phases, as a low-risk awareness test.
- To validate security-awareness training effectiveness.
- Combined with the credential-hygiene audit.

## Prerequisites

- Authorization for clipboard monitoring on test hosts; user notification per the ROE.
- Canary credentials for controlled tests.

## Procedure

1. Deploy a canary clipboard monitor on test hosts (authorized, time-boxed).
2. Measure: how often do password/token-shaped strings appear on clipboards?
3. Plant canary credentials via authorized test users and verify capture.
4. Check for clipboard-manager tools and cloud clipboard sync (a sync service holding
   credentials).
5. Correlate with awareness training: do trained users still copy passwords?
6. Remove the monitor; deliver the clipboard-exposure assessment with training
   recommendations.

## Expected outputs

- Clipboard credential-exposure statistics.
- Clipboard-sync and manager-tool findings.
- Awareness-training effectiveness notes.

## Pitfalls

- Monitoring clipboards without user notification where required — check the ROE.
- Storing captured clipboard contents beyond the analysis — aggregate statistics,
  destroy samples.
- Forgetting cloud clipboard sync as an exfil path — include it.

## References

- MITRE ATT&CK: Input Capture — Clipboard Data (T1115).

## Blue-team control under test

This playbook validates their credential-hygiene culture is what's measured — clipboard
passwords are a training and tooling finding, not a malware finding. Paired blue-team
counterpart: `cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
