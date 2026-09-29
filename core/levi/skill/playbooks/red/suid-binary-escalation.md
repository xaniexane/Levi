---
skill_id: red_suid_binary_escalation
name: SUID Binary Escalation Test
description: Test SUID/SGID binary abuse for privilege escalation on Linux hosts.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, linux, suid]
version: 1.0.0
team: red
tests_blue: cyber_core_privilege_escalation_sudo
---
# SUID Binary Escalation Test

## Purpose

SUID binaries run as their owner — usually root. Non-standard SUID binaries and known-
abusable ones (via GTFOBins) are a classic Linux privesc path. This test inventories
SUID/SGID binaries and validates each against abuse techniques with inert proofs.

## When to use

- During Linux privilege-escalation phases.
- To validate the SUID inventory against a hardened baseline.
- After software installs that may have added SUID binaries.

## Prerequisites

- Authorization for privilege escalation on the targets.
- Inert proofs only (canary file reads as root).

## Procedure

1. Inventory all SUID/SGID binaries (`find / -perm -4000`) and compare against the hardened
   baseline; flag non-standard entries.
2. Check each against GTFOBins-style abuse techniques; test with inert payloads.
3. Look for SUID binaries with relative-path or environment-variable flaws (PATH hijacking,
   LD_PRELOAD).
4. Verify each successful escalation with a canary root-file read.
5. Record which binaries the EDR/auditd flagged during abuse.
6. Deliver the SUID findings with remediation (remove SUID bit, use capabilities).

## Expected outputs

- SUID/SGID inventory with baseline delta.
- Per-binary abuse feasibility with proof.
- Remediation per binary (chmod u-s, capabilities).

## Pitfalls

- Removing SUID bits during the test and breaking applications — report, don't
  remediate, without approval.
- Missing SGID and capabilities (`getcap`) while focusing only on SUID.
- Environment-variable attacks that affect other users' sessions — test carefully.

## References

- MITRE ATT&CK: Setuid and Setgid (T1548.001); GTFOBins (public).

## Blue-team control under test

This playbook validates their Linux hardening baseline should define the allowed SUID
set — every extra binary is a finding, every abusable one is critical. Paired blue-team
counterpart:
`cyber_core_privilege_escalation_sudo`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
