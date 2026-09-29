---
skill_id: red_steganographic_exfil_test
name: Steganographic Exfiltration Test
description: Test image-embedded exfiltration to validate DLP content-inspection depth.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, steganography, dlp]
version: 1.0.0
team: red
tests_blue: cyber_performing_steganography_detection
---
# Steganographic Exfiltration Test

## Purpose

Hiding data in images defeats content inspection that only reads text. This test
exfiltrates canary data embedded in images through email, web, and cloud channels,
validating DLP's content-depth honestly.

## When to use

- During advanced exfiltration phases.
- To validate DLP image-analysis capabilities.
- Paired with the steganography C2 test.

## Prerequisites

- Authorization for exfiltration testing; canary data in canary images.
- DLP-team coordination.

## Procedure

1. Embed canary data in images (LSB and transform-domain).
2. Exfiltrate via email attachments, web uploads, and cloud storage (canary destinations).
3. Record DLP verdicts per channel and per embedding method.
4. Test DLP image OCR/hash analysis against the carriers.
5. Destroy all carriers and recovered data.
6. Deliver the steganographic-exfiltration assessment with realistic scoping.

## Expected outputs

- Per-channel/per-method DLP results.
- Image-analysis capability findings.
- Scoping recommendations (endpoint vs. content).

## Pitfalls

- Real data in carriers — canary only.
- Presenting undetectability as the conclusion — endpoint controls are the honest
  recommendation.

## References

- MITRE ATT&CK: Steganography (T1027.003).

## Blue-team control under test

This playbook validates their DLP content depth is honestly assessed — the usual outcome
scopes detection to the endpoint. Paired blue-team counterpart:
`cyber_performing_steganography_detection`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
