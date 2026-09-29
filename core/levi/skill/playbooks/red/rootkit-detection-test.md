---
skill_id: red_rootkit_detection_test
name: Rootkit Detection Validation Test
description: Test rootkit-style hiding techniques in a lab to validate integrity monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, rootkit, lab]
version: 1.0.0
team: red
tests_blue: cyber_implementing_file_integrity_monitoring_with_aide
---
# Rootkit Detection Validation Test

## Purpose

Rootkits hide by subverting the OS's own reporting. This lab test deploys canary hiding
techniques (userland hooks, DKOM concepts) and validates whether integrity monitoring,
cross-view detection, and offline analysis catch the deception.

## When to use

- Lab-only, during advanced defense-evasion phases.
- To validate boot integrity (Secure Boot, measured boot) and offline-analysis
  capability.
- When the threat model includes kernel-level adversaries.

## Prerequisites

- Isolated lab VMs with snapshots; explicit authorization for kernel techniques.
- Inert hiding: canary processes/files hidden, nothing destructive.

## Procedure

1. Snapshot the lab VM; deploy a userland hiding canary (API-hook process hiding) and test
   detection via cross-view (tasklist vs. direct handle enumeration).
2. Test bootkit concepts discussion-only unless the lab is specifically built for it —
   validate Secure Boot and measured-boot attestation instead.
3. Run the EDR and an offline disk analysis against the VM; compare what each sees.
4. Record which hiding techniques were caught by which layer.
5. Restore the snapshot; verify the VM is clean.
6. Deliver the integrity-monitoring assessment with boot-attestation recommendations.

## Expected outputs

- Per-technique hiding vs. detection matrix.
- Online vs. offline analysis comparison.
- Boot-integrity recommendations.

## Pitfalls

- Kernel techniques outside the snapshot-capable lab — never on real hardware.
- Deploying real rootkits 'for realism' — canary hiding techniques only.
- Forgetting the offline analysis — cross-view is the detection principle being
  validated.

## References

- MITRE ATT&CK: Rootkit (T1014).

## Blue-team control under test

This playbook validates their integrity monitoring and offline-analysis capability are
under test — hiding the EDR can't see from inside is proven from outside. Paired blue-
team counterpart: `cyber_implementing_file_integrity_monitoring_with_aide`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
