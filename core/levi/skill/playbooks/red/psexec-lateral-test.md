---
skill_id: red_psexec_lateral_test
name: PsExec-Style Lateral Movement Test
description: Test PsExec-style lateral movement to validate SMB and service-creation monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, psexec, smb]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_smb
---
# PsExec-Style Lateral Movement Test

## Purpose

PsExec-style movement — SMB admin shares plus remote service creation — is the noisiest
lateral technique and therefore the detection baseline. This test validates that
7045/4624 telemetry and EDR catch it, establishing the floor every stealthier technique
is measured against.

## When to use

- During lateral-movement phases, first technique tested.
- To establish the detection baseline before stealthier variants.
- To validate SMB signing and admin-share controls.

## Prerequisites

- Authorization for lateral movement between the named hosts.
- Inert remote payload (canary file write on the target).

## Procedure

1. Execute PsExec-style movement to the target host with the authorized credential, running
   an inert canary.
2. Record the full telemetry: 4624 logon type 3, 7045 service creation, SMB sessions, EDR
   alerts.
3. Test variants: custom service names vs. default, renamed binaries.
4. Verify the canary executed on the target; clean the service and canary.
5. Measure detection latency from service creation to alert.
6. Deliver the lateral-movement baseline: this is the floor.

## Expected outputs

- PsExec-telemetry record (4624/7045/SMB/EDR).
- Variant detection comparison.
- Detection-latency measurement.

## Pitfalls

- Lateral movement outside the named hosts — scope is the authorization.
- Leaving remote services installed — clean every target.
- Forgetting the credential used — log which credential moved where.

## References

- MITRE ATT&CK: Lateral Movement via service execution; PsExec documentation.

## Blue-team control under test

This playbook validates their lateral-movement detection floor is established here — if
PsExec-style movement goes silent, deeper techniques are untestable. Paired blue-team
counterpart:
`cyber_core_lateral_movement_smb`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
