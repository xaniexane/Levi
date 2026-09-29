---
skill_id: red_lsass_dump_test
name: LSASS Dump Detection Test
description: Test LSASS memory-dump techniques to validate credential-access monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, lsass, monitoring]
version: 1.0.0
team: red
tests_blue: cyber_detecting_credential_dumping_techniques
---
# LSASS Dump Detection Test

## Purpose

LSASS holds credentials in memory; dumping it is the canonical credential-theft
technique. This test runs the dump family — Task Manager, procdump, comsvcs, direct API
— with the goal of mapping exactly which paths the EDR blocks, alerts on, or misses.

## When to use

- During credential-access phases on Windows.
- To build a per-technique LSASS-access detection matrix.
- To validate Protected Process Light and Credential Guard coverage.

## Prerequisites

- Authorization for LSASS access on test hosts; explicit approval for the privilege
  level.
- Inert goal: dump handle opened, canary credential marker — full credential extraction
  only where explicitly authorized.

## Procedure

1. For each dump technique (Task Manager UI, procdump -ma, comsvcs MiniDump, direct
   MiniDumpWriteDump, Dumpert-style), attempt LSASS access on the test host.
2. Record per technique: blocked, alerted, or silent — with Sysmon event 10 details.
3. Test with Credential Guard / PPL enabled vs. disabled to show the control's effect.
4. Verify whether any technique produced a usable dump (handle the dump file per the
   credential ROE).
5. Securely delete all dump artifacts; verify deletion.
6. Deliver the LSASS-access matrix with hardening recommendations (Credential Guard
   rollout, PPL).

## Expected outputs

- Per-technique LSASS-access outcome matrix.
- Control-effectiveness comparison (Credential Guard/PPL on vs. off).
- Dump-artifact destruction log.

## Pitfalls

- Full credential extraction without explicit approval — scope the goal first.
- Dump files left on disk — they're credential material, destroy per the ROE.
- Testing on production domain controllers without a dedicated window.

## References

- MITRE ATT&CK: OS Credential Dumping — LSASS Memory (T1003.001).

## Blue-team control under test

This playbook validates their LSASS protection stack is under test — every silent dump
path is a Credential Guard or EDR-rule gap. Paired blue-team counterpart:
`cyber_detecting_credential_dumping_techniques`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
