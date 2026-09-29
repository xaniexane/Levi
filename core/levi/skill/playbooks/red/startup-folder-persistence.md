---
skill_id: red_startup_folder_persistence
name: Startup Folder Persistence Test
description: Test startup-folder persistence (including LNK abuse) to validate file-monitoring and user-awareness controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, startup-folder]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_startup_folder_persistence
---
# Startup Folder Persistence Test

## Purpose

The startup folder is the simplest user-level persistence: drop a shortcut, wait for
logon. Testing it validates file-integrity monitoring of autostart locations and whether
users notice or report unexpected startup items.

## When to use

- During persistence phases on user workstations.
- To validate FIM coverage of per-user autostart paths.
- Combined with the removable-media test for a full user-vector exercise.

## Prerequisites

- Authorization for the target workstations; user notification plan per the ROE.
- Inert LNK/shortcut payloads only.

## Procedure

1. Place an inert shortcut in the user's startup folder pointing at a canary executable.
2. Test LNK argument abuse: shortcut with hidden-window arguments and icon spoofing.
3. Log off/on and verify the canary executed.
4. Record telemetry: FIM alerts on the startup folder, EDR process-ancestry (explorer.exe →
   canary).
5. Check whether the user noticed or reported the new startup item.
6. Remove the shortcut and canary; verify the folder is clean.

## Expected outputs

- Startup-folder detection matrix (FIM, EDR, user report).
- Execution-verification evidence.
- Cleanup verification.

## Pitfalls

- Placing items in all-users startup without authorization for the privilege level.
- Icon-spoofed LNKs that users can't distinguish — that's the point of the test, but
  debrief affected users.
- Forgetting the registry-run-key overlap — test locations independently for clean
  telemetry.

## References

- MITRE ATT&CK: Boot or Logon Autostart Execution — Shortcut Modification (T1547.009).

## Blue-team control under test

This playbook validates their FIM coverage of autostart locations and user reporting
both get tested — silent persistence here is a monitoring and awareness gap. Paired
blue-team counterpart: `cyber_hunting_for_startup_folder_persistence`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
