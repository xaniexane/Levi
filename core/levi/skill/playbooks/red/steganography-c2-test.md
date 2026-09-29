---
skill_id: red_steganography_c2_test
name: Steganography C2 Validation Test
description: Test steganographic C2 channels to validate content-inspection controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, steganography]
version: 1.0.0
team: red
tests_blue: cyber_performing_steganography_detection
---
# Steganography C2 Validation Test

## Purpose

Steganography hides C2 in images, audio, and documents — content inspection's hardest
case. This test moves canary tasking through steganographic channels and validates
whether any content analysis notices.

## When to use

- During advanced C2 phases.
- To validate DLP content-inspection depth.
- When the threat model includes steganography-aware actors.

## Prerequisites

- Authorization for the test; canary images and carriers.
- DLP-team coordination.

## Procedure

1. Embed canary tasking in images via standard steganographic tools.
2. Move the carriers through the monitored channels (email, web upload, cloud storage).
3. Record: did DLP/content-inspection flag anything? Did file-hash or perceptual-hash
   analysis trigger?
4. Test the reverse: canary exfil hidden in outbound images.
5. Destroy all canary carriers.
6. Deliver the steganography assessment with realistic expectations (detection is hard;
   focus on endpoint).

## Expected outputs

- Steganographic-channel detection results per channel.
- DLP content-depth findings.
- Endpoint-focused recommendations.

## Pitfalls

- Real sensitive data in carriers — canary tasking only.
- Presenting steganography as undetectable — endpoint behavior still catches the
  implant.

## References

- MITRE ATT&CK: Steganography (T1027.003).

## Blue-team control under test

This playbook validates their content inspection meets its hardest case — the honest
finding is usually 'detect at the endpoint, not the carrier'. Paired blue-team
counterpart: `cyber_performing_steganography_detection`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
