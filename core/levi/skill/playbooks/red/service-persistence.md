---
skill_id: red_service_persistence
name: Windows Service Persistence Test
description: Test service-based persistence to validate service-installation monitoring (event 7045).
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, services]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_malware_persistence_with_autoruns
---
# Windows Service Persistence Test

## Purpose

Malicious services persist with SYSTEM privileges and blend into legitimate service
noise. Testing service-based persistence validates 7045 service-install logging, binary-
path auditing, and the blue team's service-baseline discipline.

## When to use

- During persistence phases requiring privileged persistence.
- To validate service-installation monitoring and allowlisted service baselines.

## Prerequisites

- Authorization for service installation with the privilege level specified.
- Service binary inert (canary writer); service names exercise-prefixed.

## Procedure

1. Install a test service with an inert binary via sc.exe; set it to auto-start.
2. Record 7045 events: service name, binary path, account, and start type.
3. Test recovery-action abuse: configure the service to run a canary on failure.
4. Verify persistence across reboots; confirm the canary executed.
5. Check whether the blue team's service baseline flagged the new service or it blended in.
6. Remove the service and binary; verify 7045-adjacent removal evidence and clean state.

## Expected outputs

- Service-install telemetry record with 7045 details.
- Baseline-blending assessment (was the new service noticed?).
- Cleanup verification.

## Pitfalls

- Service binaries left on disk after service removal — clean both.
- Testing on domain controllers or critical servers without specific approval.
- Recovery-action payloads that loop and destabilize the host — keep canaries single-
  shot.

## References

- MITRE ATT&CK: System Services — Service Execution (T1569.002).

## Blue-team control under test

This playbook validates their service-install monitoring and baseline discipline are
under test — a new SYSTEM service nobody noticed is a visibility failure. Paired blue-
team counterpart: `cyber_analyzing_malware_persistence_with_autoruns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
