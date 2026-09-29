---
skill_id: red_defacement_impact_test
name: Website Defacement Impact Test
description: Test web-defacement scenarios to validate web-integrity monitoring and recovery.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, impact, defacement, web]
version: 1.0.0
team: red
tests_blue: cyber_implementing_file_integrity_monitoring_with_aide
---
# Website Defacement Impact Test

## Purpose

Defacement is reputational impact with a technical path. This test validates web-content
integrity monitoring and the recovery path using canary defacements on staging — never
production.

## When to use

- During impact phases, against staging/test web properties.
- To validate file-integrity monitoring on web roots.
- To test the web-recovery runbook.

## Prerequisites

- Authorization for the staging web properties; canary defacement content.
- Web-team coordination.

## Procedure

1. Deploy canary defacement content to the staging web root via the authorized path.
2. Measure detection: FIM alerts, uptime/content monitoring, SOC notification time.
3. Execute the web-recovery runbook: time to restore, integrity verification.
4. Test the attack path that enabled it (writable web root, compromised CMS creds) — report
   separately.
5. Verify staging is clean and the runbook updated.
6. Deliver the defacement-readiness report.

## Expected outputs

- Defacement-detection timeline.
- Recovery measurements.
- Attack-path findings.

## Pitfalls

- Production web properties — staging only.
- Offensive defacement content — neutral canary content.

## References

- MITRE ATT&CK: Defacement (T1491).

## Blue-team control under test

This playbook validates their web-integrity monitoring is drilled — detection and
recovery time are the scored outcomes. Paired blue-team counterpart:
`cyber_implementing_file_integrity_monitoring_with_aide`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
