---
skill_id: red_pass_the_hash_test
name: Pass-the-Hash Test
description: Test pass-the-hash lateral movement to validate NTLM monitoring and credential hygiene.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, pass-the-hash, ntlm]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_rdp
---
# Pass-the-Hash Test

## Purpose

Pass-the-hash moves laterally with a hash instead of a password — no cracking needed.
This test validates NTLM auditing, signs of PtH (logon type 3 with NTLM, missing
4624/4648 pairs), and whether Credential Guard blocks it.

## When to use

- During lateral-movement phases on Windows.
- To validate NTLM monitoring and the case for NTLM restriction.
- To test Credential Guard effectiveness.

## Prerequisites

- Authorization for hash-based authentication; hashes handled per the credential ROE.
- Explicit approval for the hash source (canary account or authorized extraction).

## Procedure

1. With the authorized NTLM hash, authenticate to the target host (SMB/WMI) without the
   password.
2. Record telemetry: 4624 type 3, NTLM audit events, EDR alerts — and the PtH indicators.
3. Test with Credential Guard enabled vs. disabled (lab) to show the control's effect.
4. Verify the canary action on the target; clean artifacts.
5. Destroy hash material per the ROE after the test.
6. Deliver the PtH assessment with NTLM-restriction recommendations.

## Expected outputs

- PtH telemetry record with indicator analysis.
- Credential Guard effectiveness comparison.
- Hash-material destruction log.

## Pitfalls

- Hash material lingering after the test — destroy per the ROE.
- Testing with Domain Admin hashes without specific approval — canary accounts first.
- Confusing PtH with overpass-the-hash — test and report separately.

## References

- MITRE ATT&CK: Use Alternate Authentication Material — Pass the Hash (T1550.002).

## Blue-team control under test

This playbook validates their NTLM monitoring and credential hygiene are under test —
silent PtH is the evidence for NTLM auditing and restriction. Paired blue-team
counterpart:
`cyber_core_lateral_movement_rdp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
