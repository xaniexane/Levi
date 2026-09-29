---
skill_id: red_wmi_event_subscription
name: WMI Event Subscription Persistence Test
description: Test fileless WMI event-subscription persistence to validate WMI auditing and EDR coverage.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, persistence, wmi, fileless]
version: 1.0.0
team: red
tests_blue: cyber_core_wmi_persistence
---
# WMI Event Subscription Persistence Test

## Purpose

WMI event subscriptions persist without files — a filter, a consumer, and a binding, all
in the WMI repository. This test validates that WMI auditing (5857-5861 events) and EDR
detect subscription creation, the classic fileless persistence defenders most often
miss.

## When to use

- During persistence phases testing fileless techniques.
- To validate WMI operational-log auditing is enabled and forwarded.
- When the threat model includes advanced persistent threats.

## Prerequisites

- Authorization for WMI persistence with dwell time and cleanup.
- WMI operational log auditing confirmed as a prerequisite check — the test also
  validates it's on.

## Procedure

1. Create an __EventFilter (e.g., timer or logon event), a CommandLineEventConsumer running
   an inert canary, and the __FilterToConsumerBinding.
2. Verify the consumer fires on the trigger event (canary evidence).
3. Record telemetry: WMI operational log events, Sysmon/EDR alerts, and whether the
   subscription was visible in standard admin tooling.
4. Test persistence across reboots (WMI repository survives).
5. Remove filter, consumer, and binding; verify the repository is clean via enumeration.
6. Deliver the WMI-auditing assessment with enablement guidance for the operational log.

## Expected outputs

- WMI subscription creation/detection matrix.
- Trigger-verification evidence.
- Repository-cleanup verification.

## Pitfalls

- Orphaned consumers or bindings after cleanup — enumerate all three classes at phase
  end.
- Assuming the WMI operational log is enabled — verify; its absence is itself a finding.
- Timer-interval triggers that fire too often and create noise — use sparse intervals.

## References

- MITRE ATT&CK: WMI Event Subscription (T1546.003).

## Blue-team control under test

This playbook validates their WMI operational-log auditing is usually the gap this test
exposes — no 5857-5861 events means fileless persistence is invisible. Paired blue-team
counterpart: `cyber_core_wmi_persistence`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
