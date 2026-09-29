---
skill_id: red_https_c2_test
name: HTTPS Command-and-Control Test
description: Test HTTPS-based C2 to validate TLS inspection and beaconing detection.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, https, c2]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_command_and_control_beaconing
---
# HTTPS Command-and-Control Test

## Purpose

HTTPS C2 hides in the web's noise. This test runs canary HTTPS beacons with varying
profiles — intervals, jitter, JA3, domain fronting concepts — and validates beaconing
detection, TLS-inspection policy, and proxy logging.

## When to use

- During C2 phases.
- To validate network beaconing analytics.
- To test TLS-inspection coverage and proxy-log completeness.

## Prerequisites

- Authorization for C2 testing; canary beacon infrastructure.
- NetOps coordination for log verification.

## Procedure

1. Run canary HTTPS beacons at fixed intervals; check beaconing analytics for detection.
2. Vary the profile: jitter, randomized intervals, domain rotation, user-agent spoofing.
3. Test TLS-inspection: is the canary traffic decrypted and logged, or does it pass opaque?
4. Record proxy logs: are the beacon domains and JA3 fingerprints visible?
5. Test long-polling and websocket variants as alternate HTTPS channels.
6. Tear down beacons; verify no test infrastructure remains.
7. Deliver the HTTPS-C2 detection assessment.

## Expected outputs

- Beaconing-detection results per profile.
- TLS-inspection coverage findings.
- Proxy-log completeness assessment.

## Pitfalls

- Beaconing at volumes that trigger upstream abuse alerts — coordinate and rate-limit.
- Real C2 frameworks' default profiles without customization — that's the attacker's
  laziness, test both.

## References

- MITRE ATT&CK: Application Layer Protocol — Web Protocols (T1071.001).

## Blue-team control under test

This playbook validates their network analytics face realistic beaconing — regular
beacons nobody flagged are a network-detection gap. Paired blue-team counterpart:
`cyber_hunting_for_command_and_control_beaconing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
