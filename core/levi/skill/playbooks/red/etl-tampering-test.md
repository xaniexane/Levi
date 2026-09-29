---
skill_id: red_etl_tampering_test
name: ETW/ETL Tampering Validation Test
description: Test ETW tampering techniques to validate sensor resilience against telemetry blinding.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, etw, telemetry]
version: 1.0.0
team: red
tests_blue: cyber_configuring_windows_event_logging_for_detection
---
# ETW/ETL Tampering Validation Test

## Purpose

ETW is the telemetry backbone most EDRs rely on; attackers blind it to go dark. This
test applies known ETW-tampering techniques in the lab and validates whether the sensor
stack detects the tampering itself, fails closed, or silently goes blind.

## When to use

- Lab-first, during defense-evasion phases.
- To validate EDR self-protection and tamper alerting.
- When the threat model includes telemetry-aware adversaries.

## Prerequisites

- Lab authorization; production only with explicit approval and sensor-health
  monitoring.
- Sensor-health baseline captured before the test.

## Procedure

1. Baseline the sensor: confirm ETW providers are flowing and the EDR reports healthy.
2. Apply ETW-tampering variants (provider patching, trace-session manipulation) per public
   techniques, each followed by a canary action that should have generated telemetry.
3. For each variant: did the EDR alert on the tampering, did it fail closed (block), or did
   the canary go silent?
4. Restore ETW state after each variant and verify sensor health returns.
5. Deliver the telemetry-resilience verdict: tamper-evident, fail-closed, or blind.

## Expected outputs

- Per-variant tampering outcome (alerted/blocked/blind).
- Sensor-health before/after evidence.
- Tamper-response recommendations.

## Pitfalls

- Leaving ETW tampered on a production host — restore and verify after every variant.
- No sensor-health baseline — without it you can't prove the tampering had an effect.
- Confusing EDR self-protection blocks with detection — record both separately.

## References

- MITRE ATT&CK: Impair Defenses — Disable Windows Event Logging (T1562.002).

## Blue-team control under test

This playbook validates their telemetry pipeline's resilience is under test — an EDR
that goes silently blind is worse than one that fails loudly. Paired blue-team
counterpart: `cyber_configuring_windows_event_logging_for_detection`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
