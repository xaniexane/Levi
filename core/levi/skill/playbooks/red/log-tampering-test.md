---
skill_id: red_log_tampering_test
name: Log Tampering and Clearing Test
description: Test event-log tampering and clearing to validate log forwarding and tamper alerting.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, defense-evasion, logs, siem]
version: 1.0.0
team: red
tests_blue: cyber_core_backup_tampering
---
# Log Tampering and Clearing Test

## Purpose

Attackers clear or tamper logs to hide; the defense is logs the attacker can't reach.
This test clears and tampers canary logs and validates that centralized forwarding
captured the events first, and that the tampering itself alerted.

## When to use

- During defense-evasion phases.
- To validate log-forwarding latency vs. attacker dwell time.
- To test SIEM rules for log-clearing events (1102, 104).

## Prerequisites

- Authorization for log manipulation on test hosts.
- SIEM forwarding confirmed as the prerequisite — the test measures it.

## Procedure

1. Generate canary events on the test host, then clear the Security log (event 1102) and
   the System log (104).
2. Check the SIEM: did the canary events arrive before the clear? Did the clear event
   itself arrive and alert?
3. Test targeted tampering: deleting specific canary events vs. wholesale clearing.
4. Measure forwarding latency: event creation → SIEM ingestion time.
5. Test log-size and retention settings: can the attacker rotate logs away before
   forwarding?
6. Deliver the log-resilience assessment with forwarding and retention recommendations.

## Expected outputs

- Forwarding-latency measurements.
- Tamper/clear detection results (1102/104 alerting).
- Retention and rotation findings.

## Pitfalls

- Clearing production logs without explicit approval — test hosts only.
- No pre-test forwarding baseline — measure the normal latency first.
- Forgetting that 1102 itself must be forwarded — the clear event is the alert.

## References

- MITRE ATT&CK: Indicator Removal — Clear Windows Event Logs (T1070.001).

## Blue-team control under test

This playbook validates their log pipeline's race against the attacker is what's
measured — events that never reach the SIEM are a forwarding-latency finding. Paired
blue-team counterpart:
`cyber_core_backup_tampering`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
