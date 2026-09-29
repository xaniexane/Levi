---
skill_id: red_firmware_impact_test
name: Firmware Impact Validation Test
description: Validate firmware-attack impact concepts in a lab to test hardware-root-of-trust controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, impact, firmware, lab]
version: 1.0.0
team: red
tests_blue: cyber_auditing_uefi_firmware_with_chipsec
---
# Firmware Impact Validation Test

## Purpose

Firmware attacks persist below the OS and survive reinstallation. This lab test
validates firmware-integrity controls — Secure Boot, measured boot, firmware update
signing — against canary firmware-tampering concepts, without bricking real hardware.

## When to use

- Lab-only, with sacrificial or virtualized hardware.
- To validate Secure Boot and measured-boot attestation.
- When the threat model includes firmware persistence.

## Prerequisites

- Lab hardware/VMs designated sacrificial; explicit authorization.
- Firmware-team/vendor coordination.

## Procedure

1. Baseline firmware measurements (PCR values, Secure Boot state) on lab systems.
2. Attempt canary firmware modifications (unsigned option ROM concepts, boot-variable
   tampering).
3. Verify which modifications Secure Boot/measured boot blocked or detected.
4. Test firmware-update signing: does the updater accept a canary unsigned image?
5. Test recovery: can the lab system recover via known-good firmware?
6. Deliver the firmware-integrity assessment.

## Expected outputs

- Firmware-tampering block/detect results.
- Update-signing verification results.
- Recovery-path findings.

## Pitfalls

- Real hardware outside the sacrificial lab — bricking risk is real.
- Disabling Secure Boot 'to test deeper' without explicit approval.

## References

- MITRE ATT&CK: Firmware Corruption (T1495); NIST SP 800-147/155.

## Blue-team control under test

This playbook validates their hardware root of trust is validated — firmware the
platform accepts unsigned is the finding. Paired blue-team counterpart:
`cyber_auditing_uefi_firmware_with_chipsec`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
