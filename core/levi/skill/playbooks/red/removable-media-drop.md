---
skill_id: red_removable_media_drop
name: Removable Media Drop Test
description: Test user and endpoint behavior with planted USB media carrying inert payloads in authorized facilities.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, physical, usb]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_usb_device_connection_history
---
# Removable Media Drop Test

## Purpose

Find out what happens when someone plugs in a found USB drive: does the endpoint block
it, does EDR fire, does the user report it? Planted drives with inert payloads answer
all three — measuring device-control policy and user behavior in one test.

## When to use

- During on-site assessments with physical social-engineering authorization.
- To validate USB device-control policies and EDR removable-media protections.
- When the threat model includes malicious insiders or visitors.

## Prerequisites

- On-site authorization naming the areas where drops are permitted.
- Inert payloads only: canary files and beacons to a controlled listener, no real
  malware.
- Agreement on how plugged-in drives are retrieved and accounted for.

## Procedure

1. Prepare USB drives with inert payloads: an autorun-style lure document (canary beacon),
   a labeled drive ('Q3 Bonuses', 'IT Survey').
2. Place drives in approved locations (parking lot, break room, lobby) and log each
   placement with time and photo.
3. Monitor the controlled listener for beacons indicating a drive was plugged in and the
   payload stage executed.
4. Track user reporting: did anyone bring the drive to security instead of plugging it in?
5. Record EDR/device-control verdicts for each insertion event from the blue team.
6. Retrieve all drives at test end; account for every unit placed.
7. Debrief: insertion rate, execution rate, report rate, and control verdicts.

## Expected outputs

- Per-drive outcome: placed → found → plugged → executed → reported.
- Device-control and EDR verdicts per insertion.
- Drive accountability log (all units retrieved).

## Pitfalls

- Unaccounted drives left behind — every unit must be retrieved; treat a missing drive
  as an incident.
- Payloads that do anything beyond beaconing — inert means inert.
- Dropping in areas outside the authorized list (executive offices, data centers)
  without specific approval.

## References

- MITRE ATT&CK: Replication Through Removable Media (T1091).

## Blue-team control under test

This playbook validates their device-control policy and EDR removable-media modules face
a real-world test — every unblocked execution is a policy or control gap. Paired blue-
team counterpart: `cyber_analyzing_usb_device_connection_history`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
