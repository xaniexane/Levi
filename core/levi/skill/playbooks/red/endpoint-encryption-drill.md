---
skill_id: red_endpoint_encryption_drill
name: Endpoint Encryption Drill
description: Drill mass endpoint-encryption scenarios to validate EDR and recovery at scale.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, impact, ransomware, endpoints]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_ransomware_encryption_mechanisms
---
# Endpoint Encryption Drill

## Purpose

Ransomware at fleet scale is a different problem than one host. This drill encrypts
canary data across lab endpoints simultaneously, validating EDR fleet-wide response,
isolation at scale, and mass-recovery procedures.

## When to use

- Lab-only fleet drill, during impact phases.
- To validate SOC fleet-wide response procedures.
- To test mass-recovery tooling and imaging pipelines.

## Prerequisites

- Lab endpoint fleet; explicit authorization for simultaneous encryption.
- Canary data on all lab endpoints.

## Procedure

1. Snapshot the lab fleet; deploy canary data.
2. Trigger simultaneous canary encryption across the fleet.
3. Measure SOC response: time to fleet-wide isolation, containment completeness.
4. Execute mass recovery: imaging pipeline throughput, data restoration.
5. Test the EDR's automated response at scale (did it keep up?).
6. Restore the fleet; deliver the mass-impact drill report.

## Expected outputs

- Fleet-wide detection/containment timeline.
- Mass-recovery throughput measurements.
- EDR-at-scale findings.

## Pitfalls

- Any production endpoint in the fleet — lab only.
- Real ransomware samples — canary encryption.
- Skipping the recovery — mass recovery is the scored outcome.

## References

- MITRE ATT&CK: Data Encrypted for Impact (T1486).

## Blue-team control under test

This playbook validates their fleet-scale response is drilled — containment and recovery
at scale are the measured outcomes. Paired blue-team counterpart:
`cyber_analyzing_ransomware_encryption_mechanisms`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
