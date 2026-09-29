---
skill_id: red_indicator_removal_audit
name: Indicator Removal Audit
description: Audit artifact/indicator-removal techniques to validate forensic completeness.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, defense-evasion, forensics, audit]
version: 1.0.0
team: red
tests_blue: cyber_building_incident_timeline_with_timesketch
---
# Indicator Removal Audit

## Purpose

Attackers systematically remove their indicators: logs, files, registry keys,
timestamps. This audit enumerates the removal techniques relevant to the environment and
validates — per technique — whether a forensic trail survives somewhere the attacker
can't reach.

## When to use

- As a DFIR readiness audit, independent of live phases.
- After incident-response tabletop exercises.
- To validate backup and immutable-logging investments.

## Prerequisites

- Inventory of log destinations, backup systems, and forensic tooling.
- No live removal needed — this is an audit of survivability, mostly.

## Procedure

1. Enumerate the removal techniques in scope: file deletion, log clearing, timestomping,
   registry cleanup, shadow-copy deletion.
2. For each, trace where evidence would survive: SIEM copies, backups, USN journal, cloud
   audit logs, EDR cloud telemetry.
3. Where survivability is unproven, run a canary removal on a test host and verify the
   surviving trail.
4. Score each technique: fully survivable, partially survivable, or evidence-destroying.
5. Deliver the forensic-survivability matrix with investment recommendations (immutable
   logging, backup scope).

## Expected outputs

- Per-technique evidence-survivability matrix.
- Canary verification results where tested.
- Investment recommendations (what to make immutable next).

## Pitfalls

- Live destructive testing on production — canary tests on test hosts only.
- Assuming backups capture the needed artifacts — verify restore and content, not just
  job success.
- Forgetting cloud audit logs as a surviving trail for on-prem removal.

## References

- MITRE ATT&CK: Indicator Removal (T1070).

## Blue-team control under test

This playbook validates their forensic survivability is what's audited — every technique
with no surviving trail is an immutable-logging investment case. Paired blue-team
counterpart: `cyber_building_incident_timeline_with_timesketch`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
