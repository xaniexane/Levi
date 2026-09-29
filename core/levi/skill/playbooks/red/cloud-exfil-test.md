---
skill_id: red_cloud_exfil_test
name: Cloud Exfiltration Test
description: Test cloud-service exfiltration paths to validate CASB and cloud DLP.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, cloud, casb]
version: 1.0.0
team: red
tests_blue: cyber_core_data_exfiltration
---
# Cloud Exfiltration Test

## Purpose

Cloud sync and storage turn exfiltration into 'normal' traffic. This test moves canary
data through cloud sync clients, storage APIs, and collaboration shares, validating CASB
and cloud-DLP detection of anomalous cloud exfil.

## When to use

- During exfiltration phases in cloud-heavy environments.
- To validate CASB upload monitoring and cloud DLP.
- To test personal-cloud-account vs. corporate-account controls.

## Prerequisites

- Authorization for exfiltration testing; canary data only.
- CASB-team coordination.

## Procedure

1. Exfiltrate canary data via corporate cloud sync, personal cloud accounts (canary), and
   direct storage APIs.
2. Test sharing-link exfil: anyone-with-link on canary data — does anything alert?
3. Record CASB and cloud-DLP verdicts per path.
4. Test large-archive uploads vs. trickle uploads.
5. Delete all canary data from cloud destinations; verify.
6. Deliver the cloud-exfiltration assessment.

## Expected outputs

- Per-path cloud-exfil detection results.
- Sharing-link alerting assessment.
- CASB coverage findings.

## Pitfalls

- Real data to personal cloud accounts — canary data only, canary accounts only.
- Sharing links left active — verify deactivation.

## References

- MITRE ATT&CK: Exfiltration Over Web Service (T1567).

## Blue-team control under test

This playbook validates their CASB and cloud DLP face normal-looking exfil — silent
canary uploads are the cloud-egress gap. Paired blue-team counterpart:
`cyber_core_data_exfiltration`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
