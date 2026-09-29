---
skill_id: red_network_share_discovery
name: Network Share Discovery Test
description: Test network-share enumeration to validate share permissions and sensitive-data exposure.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, shares, smb]
version: 1.0.0
team: red
tests_blue: cyber_configuring_windows_event_logging_for_detection
---
# Network Share Discovery Test

## Purpose

Open shares are where credentials, PII, and backups live unprotected. This test
enumerates shares across the environment, samples permissions, and validates whether
share-access auditing and data-classification controls work.

## When to use

- During discovery phases on Windows networks.
- To validate share-permission hygiene and auditing.
- Combined with the sensitive-data discovery test.

## Prerequisites

- Authorization for share enumeration; read-only sampling.
- Agreement on sampling depth (listing vs. content sampling).

## Procedure

1. Enumerate shares on target hosts and file servers (net view, SMB enumeration).
2. Sample share permissions: which shares grant Everyone/Authenticated Users write?
3. Sample content (canary-named files first): look for credential files, PII patterns,
   backup files.
4. Record access auditing: did the sampling generate 5140/5145 events, and did anyone
   review them?
5. Check for administrative shares and their exposure.
6. Deliver the share-hygiene report with permission fixes and auditing recommendations.

## Expected outputs

- Share inventory with permission analysis.
- Content-sampling findings (canary-first).
- Share-access auditing assessment.

## Pitfalls

- Deep content crawling of user shares without approval — sample, don't vacuum.
- Opening files with live malware — canary patterns and metadata first.
- Forgetting that share enumeration itself is logged — that's part of the test.

## References

- MITRE ATT&CK: Network Share Discovery (T1135).

## Blue-team control under test

This playbook validates their file-share hygiene is under test — Everyone-write shares
with credentials inside are findings that predate any exploit. Paired blue-team
counterpart: `cyber_configuring_windows_event_logging_for_detection`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
