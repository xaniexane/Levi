---
skill_id: red_dns_c2_test
name: DNS Command-and-Control Test
description: Test DNS-based C2 channels to validate DNS monitoring and filtering.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, dns, c2]
version: 1.0.0
team: red
tests_blue: cyber_core_c2_beaconing
---
# DNS Command-and-Control Test

## Purpose

DNS is the protocol most likely to be allowed out — making it the classic covert
channel. This test exercises DNS tunneling and DNS-based C2 signaling with canary
traffic, validating DNS logging, tunneling detection, and resolver policy.

## When to use

- During C2 phases.
- To validate DNS security monitoring (query volume, entropy, tunneling heuristics).
- To test DNS filtering/allowlisting effectiveness.

## Prerequisites

- Authorization for covert-channel testing; canary C2 infrastructure in the lab.
- DNS-team coordination for log verification.

## Procedure

1. Stand up canary DNS C2 infrastructure (lab authoritative server).
2. Exercise DNS tunneling with canary data at varying volumes and encoding densities.
3. Test DNS-based signaling (TXT queries, subdomain encoding) separately from bulk
   tunneling.
4. Record detection: DNS logs, tunneling heuristics, firewall DNS-inspection alerts.
5. Test against the filtering policy: are unauthorized resolvers (DoH/DoT) reachable?
6. Tear down the canary infrastructure; verify no test domains remain active.
7. Deliver the DNS-channel assessment with monitoring recommendations.

## Expected outputs

- Per-technique DNS detection results.
- Volume/entropy detection thresholds observed.
- DoH/DoT bypass findings.

## Pitfalls

- Real C2 infrastructure outside the lab — canary infrastructure only.
- High-volume tunneling that impacts DNS performance — rate-limit the test.
- Forgetting to tear down test domains — verify deactivation.

## References

- MITRE ATT&CK: Application Layer Protocol — DNS (T1071.004), DNS tunneling literature.

## Blue-team control under test

This playbook validates their DNS monitoring is under test — high-entropy query streams
nobody flagged are a DNS-security gap. Paired blue-team counterpart:
`cyber_core_c2_beaconing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
