---
skill_id: red_wireless_recon
name: Wireless Reconnaissance
description: Survey wireless networks around authorized facilities to find rogue APs, weak encryption, and misconfigured enterprise Wi-Fi.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, wireless]
version: 1.0.0
team: red
tests_blue: cyber_performing_wireless_security_assessment_with_kismet
---
# Wireless Reconnaissance

## Purpose

Map the wireless landscape in and around the authorized facility: corporate SSIDs, guest
networks, rogue access points, and neighboring networks that could be attack vectors.
Wireless is often the soft perimeter — this survey tells the blue team what their
airspace actually looks like.

## When to use

- During on-site assessments where wireless is in scope.
- To hunt rogue APs and evil twins before the wireless attack phase.
- To validate WPA2-Enterprise configuration and certificate validation behavior.

## Prerequisites

- On-site authorization with the physical areas and times defined.
- Passive monitoring only in this phase — no deauthentication or association without the
  attack-phase authorization.
- Local radio regulations acknowledged (passive receive is fine; transmission rules
  vary).

## Procedure

1. Perform a passive wardrive/walkthrough with a monitor-mode adapter, recording SSIDs,
   BSSIDs, channels, signal strength, and encryption types (use kismet/airodump-ng style
   tooling).
2. Identify the corporate SSIDs and map their coverage, channel overlap, and signal leakage
   outside the facility.
3. Flag rogue APs: BSSIDs broadcasting corporate SSIDs that are not in the blue team's AP
   inventory.
4. Capture WPA handshakes passively only where authorized for later offline analysis —
   never force deauthentications in the recon phase.
5. Test enterprise Wi-Fi behavior from a client perspective: does the supplicant validate
   the RADIUS certificate, or will it connect to any AP with the right SSID?
6. Correlate findings with the blue team's wireless inventory and produce the rogue-AP list
   with locations and signal data.

## Expected outputs

- Wireless survey map: SSIDs, BSSIDs, encryption, signal heatmap.
- Rogue AP findings with location estimates.
- Enterprise Wi-Fi misconfiguration notes (cert validation, weak EAP methods).

## Pitfalls

- Accidentally transmitting (probing, associating) during a passive-only phase — use
  monitor mode and verify no TX.
- Capturing neighboring networks' traffic content — record metadata only, per the ROE
  and local law.
- Missing 5/6 GHz bands — survey all bands the facility uses.

## References

- MITRE ATT&CK: Network Service Discovery via wireless (T1046); Rogue AP techniques.
- Wi-Fi Alliance: enterprise configuration guidance.

## Blue-team control under test

This playbook validates their wireless IDS should corroborate the rogue-AP list — rogues
found by red but missed by WIDS are a detection gap. Paired blue-team counterpart:
`cyber_performing_wireless_security_assessment_with_kismet`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
