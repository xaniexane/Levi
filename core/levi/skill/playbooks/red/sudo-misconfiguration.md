---
skill_id: red_sudo_misconfiguration
name: Sudo Misconfiguration Escalation Test
description: Test sudo misconfigurations (NOPASSWD, wildcard commands) for privilege escalation on Linux.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, linux, sudo]
version: 1.0.0
team: red
tests_blue: cyber_core_privilege_escalation_sudo
---
# Sudo Misconfiguration Escalation Test

## Purpose

Sudo is the gatekeeper on Linux, and its configuration is frequently the vulnerability.
This test enumerates sudo rights (`sudo -l`) and exploits misconfigurations — NOPASSWD,
wildcard commands, editable scripts — to validate sudoers hygiene.

## When to use

- During Linux privilege-escalation phases.
- To validate sudoers baselines across the fleet.
- After gaining any low-privilege Linux shell.

## Prerequisites

- Authorization for privilege escalation on the Linux targets.
- Low-privilege test accounts with representative sudo rights.

## Procedure

1. Enumerate with `sudo -l` and inspect /etc/sudoers.d/ for NOPASSWD entries, wildcards,
   and dangerous binaries (vim, less, find, awk).
2. Exploit GTFOBins-style sudo abuses with inert proof (read a canary root-owned file).
3. Test wildcard command abuse: can arguments be injected past the intended command?
4. Check for editable scripts run via sudo — a writable script is root execution.
5. Record which misconfigurations yielded root and which were properly constrained.
6. Deliver per-host sudoers findings with corrected sudoers snippets.

## Expected outputs

- Sudo misconfiguration inventory per host.
- Root-proof evidence per exploitable entry.
- Corrected sudoers configurations.

## Pitfalls

- Modifying sudoers during the test and breaking admin access — read-only enumeration
  plus inert proofs.
- Assuming `sudo -l` shows everything — inspect the included files too.
- Forgetting LDAP/SSSD-provided sudo rules in enterprise environments.

## References

- MITRE ATT&CK: Sudo and Sudo Caching (T1548.003); GTFOBins (public).

## Blue-team control under test

This playbook validates their sudoers baseline is the control under test — every
NOPASSWD wildcard is a configuration finding with a known fix. Paired blue-team
counterpart:
`cyber_core_privilege_escalation_sudo`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
