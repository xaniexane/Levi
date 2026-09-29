---
skill_id: red_drive_by_download_simulation
name: Drive-By Download Simulation
description: Simulate drive-by download attacks in a lab to test browser and endpoint controls without endangering users.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, browser, lab]
version: 1.0.0
team: red
tests_blue: cyber_core_drive_by_download
---
# Drive-By Download Simulation

## Purpose

Test whether a compromised or malicious website could silently drop malware on corporate
endpoints — entirely in the lab. The simulation measures browser hardening, EDR, and
network filtering against the drive-by attack chain without ever exposing real users.

## When to use

- To validate browser hardening baselines and EDR web-protection features.
- When the threat model includes watering-hole or malvertising scenarios.
- As a lab exercise — this technique is never tested against real users.

## Prerequisites

- Lab-only authorization: isolated VMs, no real user endpoints, no internet-facing lure
  pages.
- EDR and browser configs under test documented as the baseline.

## Procedure

1. Build the lab: victim VMs with the corporate browser/EDR baseline, attacker VM serving
   the simulated exploit kit (inert payloads only).
2. Simulate the attack chain stages: lure page → browser exploit attempt (patched-CVE
   proof-of-concept, inert) → payload download → execution attempt.
3. Record at each stage which control fired: browser sandbox, SmartScreen/safe-browsing,
   EDR, network filtering.
4. Vary the chain: different browsers, with and without EDR, patched vs. unpatched
   baselines.
5. Measure time-to-detect and time-to-block per stage.
6. Translate lab results into hardening recommendations for the production baseline.

## Expected outputs

- Per-stage control matrix across browser/EDR configurations.
- Time-to-detect/block measurements.
- Hardening recommendations for the browser baseline.

## Pitfalls

- Letting the simulation touch real users or the internet — lab isolation is the safety
  control.
- Using live exploit kits instead of inert simulations — the chain stages are what
  matter, not real exploitation.
- Testing only the default browser — cover every browser in the corporate baseline.

## References

- MITRE ATT&CK: Drive-by Compromise (T1189).

## Blue-team control under test

This playbook validates their browser baseline and EDR web protections get a stage-by-
stage scorecard — silent progression through all stages is a layered-defense failure.
Paired blue-team counterpart:
`cyber_core_drive_by_download`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
