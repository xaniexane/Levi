---
skill_id: red_dos_resilience_test
name: Denial-of-Service Resilience Test
description: Test DoS resilience with controlled load to validate mitigation and capacity planning.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, impact, dos, resilience]
version: 1.0.0
team: red
tests_blue: cyber_implementing_ddos_mitigation_with_cloudflare
---
# Denial-of-Service Resilience Test

## Purpose

DoS is impact without intrusion. This controlled test applies agreed load levels against
staging or explicitly authorized targets, validating DDoS mitigation, rate limiting, and
capacity headroom — never as an uncontrolled flood.

## When to use

- During impact phases, with explicit load-testing authorization.
- To validate DDoS-mitigation service effectiveness.
- To measure capacity headroom before peak seasons.

## Prerequisites

- Explicit authorization with load ceilings, time windows, and target scope.
- NetOps and mitigation-vendor coordination.

## Procedure

1. Ramp load gradually against the authorized target within the agreed ceiling.
2. At each level, measure: availability, latency, mitigation engagement.
3. Test layer-7 patterns (slowloris-style, expensive endpoints) separately from volumetric.
4. Verify the mitigation service's detection and scrubbing behavior.
5. Stop at the ceiling or at first customer impact — whichever comes first.
6. Deliver the DoS-resilience report with capacity recommendations.

## Expected outputs

- Load-vs-availability measurements per level.
- Mitigation-engagement analysis.
- Capacity recommendations.

## Pitfalls

- Exceeding the load ceiling — the ceiling is the authorization.
- Testing production without explicit approval and a maintenance window.
- Layer-7 tests that look like real attacks to upstream providers — coordinate.

## References

- MITRE ATT&CK: Network Denial of Service (T1498).

## Blue-team control under test

This playbook validates their DoS mitigation gets measured, not assumed — the load level
where mitigation engages is the finding. Paired blue-team counterpart:
`cyber_implementing_ddos_mitigation_with_cloudflare`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
