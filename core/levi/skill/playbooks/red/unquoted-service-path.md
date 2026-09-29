---
skill_id: red_unquoted_service_path
name: Unquoted Service Path Escalation Test
description: Test unquoted service paths for privilege escalation to validate service-configuration auditing.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, windows, services]
version: 1.0.0
team: red
tests_blue: cyber_hardening_windows_endpoint_with_cis_benchmark
---
# Unquoted Service Path Escalation Test

## Purpose

Services with unquoted binary paths containing spaces can be hijacked by planting an
executable earlier in the path — running as SYSTEM on restart. This test finds such
services and validates that service-configuration auditing would catch the exploitation.

## When to use

- During Windows privilege-escalation phases.
- To validate service binary-path quoting across the fleet.
- As a low-noise privesc test before noisier techniques.

## Prerequisites

- Authorization for privilege escalation on the targets.
- Write access to the hijack location confirmed as part of the test (that's the
  vulnerability).

## Procedure

1. Enumerate services with unquoted paths containing spaces (`wmic service get
   name,pathname` filtered).
2. For each candidate, check write permissions on each path component — only writable
   components are exploitable.
3. Plant an inert executable at the hijackable path location.
4. Restart the service (as authorized) and verify the canary executed as SYSTEM.
5. Record telemetry: service-control events, process ancestry (services.exe → canary as
   SYSTEM).
6. Remove the planted binary; recommend quoting fixes per service.

## Expected outputs

- Exploitable unquoted-path services with permission evidence.
- SYSTEM-execution proof (canary).
- Per-service remediation (quoted paths).

## Pitfalls

- Restarting critical services without a maintenance window — coordinate.
- Planting in system directories without explicit authorization for the location.
- Missing the secondary path components — check every space-separated segment.

## References

- MITRE ATT&CK: Hijack Execution Flow — Path Interception by Unquoted Path (T1574.009).

## Blue-team control under test

This playbook validates their service-configuration baseline should have no unquoted
paths — each one found is a hardening gap with a one-line fix. Paired blue-team
counterpart: `cyber_hardening_windows_endpoint_with_cis_benchmark`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
