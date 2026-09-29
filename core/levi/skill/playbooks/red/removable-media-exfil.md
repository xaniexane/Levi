---
skill_id: red_removable_media_exfil
name: Removable Media Exfiltration Test
description: Test USB/removable-media exfiltration to validate device-control policies.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, usb, device-control]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Removable Media Exfiltration Test

## Purpose

USB exfiltration bypasses every network control. This test copies canary data to
authorized test media and validates device-control enforcement: blocked, read-only, or
silently permitted.

## When to use

- During exfiltration phases.
- To validate USB device-control GPOs and DLP endpoint policies.
- Combined with the BadUSB test for the full media-vector picture.

## Prerequisites

- Authorization for removable-media use; canary data only; test USB devices.
- Endpoint-team coordination.

## Procedure

1. Attempt canary-data copies to test USB devices on sample hosts.
2. Record per host: blocked, read-only, encrypted-only enforcement, or allowed.
3. Test bypass variants: MTP phones, SD cards, USB-CDROM emulation (authorized).
4. Check DLP endpoint: did the canary copy trigger endpoint DLP?
5. Verify no canary data remains on test media after the exercise (wipe).
6. Deliver the device-control assessment.

## Expected outputs

- Per-host device-control enforcement results.
- Bypass-variant findings.
- Endpoint-DLP results.

## Pitfalls

- Real data on test media — canary data only.
- Test media leaving the facility with canary data — wipe and verify.
- Forgetting non-USB removable paths (SD, MTP) — cover the variants.

## References

- MITRE ATT&CK: Exfiltration Over Physical Medium (T1052).

## Blue-team control under test

This playbook validates their device-control policy meets reality — silently permitted
copies are the endpoint gap. Paired blue-team counterpart:
`cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
