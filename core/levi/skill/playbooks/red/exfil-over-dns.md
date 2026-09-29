---
skill_id: red_exfil_over_dns
name: DNS Exfiltration Test
description: Test DNS exfiltration to validate DNS monitoring and data-loss controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, dns, dlp]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_dns_logs_for_exfiltration
---
# DNS Exfiltration Test

## Purpose

DNS exfiltration moves data out through queries — the channel most environments barely
monitor. This test exfiltrates canary data via DNS and validates tunneling detection,
query logging, and DLP's DNS blindness.

## When to use

- During exfiltration phases.
- To validate DNS tunneling/exfiltration detection.
- To prove the DLP's DNS blind spot (or lack of one).

## Prerequisites

- Authorization for exfiltration testing; canary data only, canary authoritative server.
- DNS-team coordination.

## Procedure

1. Exfiltrate canary data via DNS TXT/NULL queries at varying rates and encoding densities.
2. Record detection: DNS logs, tunneling heuristics, DLP alerts (expect DLP silence —
   document it).
3. Test chunking and compression effects on detectability.
4. Measure maximum exfil rate before alerting (the detection threshold).
5. Tear down the canary server; verify no test domains remain.
6. Deliver the DNS-exfiltration assessment with monitoring recommendations.

## Expected outputs

- DNS exfiltration detection results per rate/encoding.
- Detection-threshold measurements.
- DLP DNS-blindness documentation.

## Pitfalls

- Real data over DNS — canary data only, always.
- Exfil rates that degrade DNS service — rate-limit.

## References

- MITRE ATT&CK: Exfiltration Over C2 Channel — DNS (T1041 variants); DNS tunneling
  literature.

## Blue-team control under test

This playbook validates their DNS monitoring and DLP face the classic blind spot —
canary data nobody noticed leaving via DNS is the finding. Paired blue-team counterpart:
`cyber_analyzing_dns_logs_for_exfiltration`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
