---
skill_id: red_icmp_tunnel_test
name: ICMP Tunnel Test
description: Test ICMP tunneling to validate non-TCP/UDP channel monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, icmp, tunneling]
version: 1.0.0
team: red
tests_blue: cyber_configuring_suricata_for_network_monitoring
---
# ICMP Tunnel Test

## Purpose

ICMP is rarely inspected — ping goes everywhere. This test tunnels canary data over ICMP
and validates whether any monitoring notices the non-standard ICMP payloads.

## When to use

- During C2 phases testing exotic channels.
- To validate firewall ICMP policies and IDS coverage.
- As the 'forgotten protocol' check.

## Prerequisites

- Authorization for tunneling tests; canary endpoints.
- NetOps awareness — ICMP anomalies may page someone.

## Procedure

1. Tunnel canary data over ICMP echo payloads between authorized endpoints.
2. Vary payload sizes and rates; record IDS/firewall reactions.
3. Check ICMP type/code policies: what's allowed out, and is it logged?
4. Test ICMPv6 variants where deployed.
5. Stop the tunnel; verify no test traffic continues.
6. Deliver the ICMP-channel assessment.

## Expected outputs

- ICMP tunneling detection results.
- Firewall ICMP-policy findings.
- Monitoring recommendations.

## Pitfalls

- Tunneling volumes that look like a ping flood — rate-limit and coordinate.
- Forgetting IPv6 — test both where deployed.

## References

- MITRE ATT&CK: Protocol Tunneling (T1572).

## Blue-team control under test

This playbook validates their forgotten-protocol monitoring is under test — silent ICMP
tunnels are the non-standard-channel gap. Paired blue-team counterpart:
`cyber_configuring_suricata_for_network_monitoring`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
