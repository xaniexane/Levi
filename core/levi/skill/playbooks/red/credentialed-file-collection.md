---
skill_id: red_credentialed_file_collection
name: Credentialed File Collection Test
description: Test automated file collection to validate DLP and file-access monitoring.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, collection, files, dlp]
version: 1.0.0
team: red
tests_blue: cyber_implementing_endpoint_dlp_controls
---
# Credentialed File Collection Test

## Purpose

Automated collection — staging documents for exfiltration — has a recognizable pattern:
bulk reads, archive creation, staging directories. This test performs canary collection
and validates whether file-access monitoring and DLP notice the staging behavior.

## When to use

- During collection phases.
- To validate DLP and file-access anomaly detection.
- Before exfiltration phases, to test the staging half.

## Prerequisites

- Authorization for bulk file operations on test data; canary files.
- DLP team coordination for the detection check.

## Procedure

1. Plant canary sensitive files across test locations.
2. Perform staged collection: bulk copy to a staging directory, archive creation, archive
   encryption.
3. Record telemetry: file-access events, DLP alerts on the canary patterns, archive-
   creation monitoring.
4. Test collection via cloud-sync folders and removable media paths (authorized).
5. Clean the staging directory and all canary files; verify.
6. Deliver the collection-behavior detection assessment.

## Expected outputs

- Collection-stage detection results per technique.
- DLP canary-pattern results.
- Cleanup verification.

## Pitfalls

- Collecting real sensitive files — canary files only.
- Archive encryption that looks like ransomware to the SOC — coordinate in advance.
- Forgetting the staging directory in cleanup — verify empty.

## References

- MITRE ATT&CK: Automated Collection (T1119), Data Staged (T1074).

## Blue-team control under test

This playbook validates their DLP and file-access monitoring face bulk-collection
behavior — silent staging is the pre-exfiltration gap. Paired blue-team counterpart:
`cyber_implementing_endpoint_dlp_controls`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
