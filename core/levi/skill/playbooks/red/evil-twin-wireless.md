---
skill_id: red_evil_twin_wireless
name: Evil-Twin Wireless Access Test
description: Stand up a rogue access point with the corporate SSID in an authorized test to measure client and NAC behavior.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, wireless, rogue-ap]
version: 1.0.0
team: red
tests_blue: cyber_conducting_wireless_network_penetration_test
---
# Evil-Twin Wireless Access Test

## Purpose

Prove what happens when an attacker broadcasts the corporate SSID: do clients connect,
does the NAC notice, does anyone alert? The evil twin runs in a controlled window with
the blue team watching — the detection race is the exercise.

## When to use

- During on-site wireless assessments with active-attack authorization.
- To validate wireless IDS rogue-AP detection and response times.
- To test whether corporate clients validate RADIUS certificates.

## Prerequisites

- Explicit authorization for rogue-AP transmission at the facility, with time window and
  channels.
- Coordination with facility management; transmission must not disrupt neighbors.
- Blue-team WIDS team on standby to measure detection time.

## Procedure

1. Survey the target SSIDs and channels from the recon phase; choose the corporate SSID
   with the weakest client validation.
2. Bring up the evil twin on an unused channel with the corporate SSID; run a captive
   portal or EAP relay listener as authorized — credentials are never harvested beyond
   proof-of-association.
3. Measure client behavior: do managed clients auto-connect, prompt, or refuse (certificate
   validation)?
4. Start the clock: how long until the WIDS flags the rogue, and how long until the blue
   team responds on the ground?
5. Attempt NAC-bypass observations only as authorized: does the rogue AP's clients get
   network access, or does NAC contain them?
6. Tear down at window end; document the full timeline from first beacon to blue-team
   response.

## Expected outputs

- Client-behavior results: auto-connect vs. prompt vs. refuse per device profile.
- Rogue-AP detection and response timeline.
- NAC containment assessment.

## Pitfalls

- Transmitting outside the authorized window or channels — interference with neighbors
  is a legal risk.
- Harvesting real credentials through the twin — proof-of-association only, per the ROE.
- Forgetting to tear down — a forgotten rogue AP becomes a real vulnerability.

## References

- MITRE ATT&CK: Wireless techniques; Rogue AP attack literature (public).

## Blue-team control under test

This playbook validates their WIDS detection time and physical-response playbook are
measured live — a twin that beacons unnoticed for the full window is a wireless-
monitoring failure. Paired blue-team counterpart:
`cyber_conducting_wireless_network_penetration_test`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
