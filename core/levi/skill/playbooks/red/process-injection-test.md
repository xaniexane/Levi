---
skill_id: red_process_injection_test
name: Process Injection Detection Test
description: Test process-injection techniques to validate EDR memory and API monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, process-injection]
version: 1.0.0
team: red
tests_blue: cyber_core_process_injection
---
# Process Injection Detection Test

## Purpose

Process injection hides malicious code inside legitimate processes. This test runs the
injection family — classic DLL injection, process hollowing, APC injection, mapping
injection — with inert payloads to map exactly which techniques the EDR sees and which
slip through.

## When to use

- During defense-evasion phases on Windows.
- To build a per-technique EDR detection matrix.
- To validate Sysmon configs (CreateRemoteThread, image-load events).

## Prerequisites

- Authorization for memory-injection techniques on test hosts.
- Inert shellcode: canary file write or beacon, no real payloads.

## Procedure

1. For each injection variant (CreateRemoteThread DLL, process hollowing, QueueUserAPC, NT-
   map-section), inject an inert canary into a test target process.
2. Record per variant: Sysmon events (8, 10, 25), EDR alert or block, and whether the
   canary executed.
3. Test both signed and unsigned target processes; note Protected Process Light boundaries.
4. Measure detection latency per variant.
5. Terminate all injected processes and verify no canary artifacts remain.
6. Deliver the per-technique detection matrix with Sysmon/EDR tuning recommendations.

## Expected outputs

- Injection-variant detection matrix (Sysmon + EDR).
- Canary-execution evidence per variant.
- Cleanup verification.

## Pitfalls

- Injecting into production processes — test targets only.
- Real payloads in the injected shellcode — inert canaries.
- Process hollowing crashing the target — snapshot or use disposable test processes.

## References

- MITRE ATT&CK: Process Injection (T1055) and sub-techniques.

## Blue-team control under test

This playbook validates their EDR's injection coverage gets a technique-by-technique
scorecard — silent variants are memory-monitoring gaps to close. Paired blue-team
counterpart: `cyber_core_process_injection`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
