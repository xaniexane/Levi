---
skill_id: red_network_scanning_nmap
name: Network Scanning with Nmap
description: Scan in-scope networks with Nmap to map live hosts, open ports, and services — the foundation every later phase builds on.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, scanning, nmap]
version: 1.0.0
team: red
tests_blue: cyber_detecting_network_reconnaissance_and_port_scanning
---
# Network Scanning with Nmap

## Purpose

Produce the authoritative map of what is reachable and listening inside the authorized
scope: live hosts, open TCP/UDP ports, service banners, and OS guesses. Done carefully,
the scan stays inside the agreed rate and window; done carelessly it looks like an
attack and disrupts fragile hosts. The scan output feeds vulnerability validation and
targeting for the whole exercise.

## When to use

- At the start of active testing against a network range, after scope is signed.
- When the blue team wants to measure whether their IDS/IPS detects and alerts on
  scanning.
- To validate the asset inventory: the scan finds the hosts nobody documented.
- Before any exploitation phase — you cannot test what you have not mapped.

## Prerequisites

- Written authorization with exact IP ranges/CIDRs, scan window, and rate limits.
- Exclusion list: fragile hosts (OT, medical, legacy) that must not be scanned
  aggressively or at all.
- Blue-team notification procedure for the scan window, per the ROE.

## Procedure

1. Start with host discovery only (`nmap -sn`) across the in-scope ranges to build the
   live-host list without touching ports.
2. Run a top-ports SYN scan (`nmap -sS --top-ports 1000`) at the agreed timing template
   (T2/T3 for fragile environments, never T5).
3. Follow up with full-port scans on hosts of interest and UDP top-ports on infrastructure
   hosts (DNS, SNMP, VPN).
4. Version-detect (`-sV`) and OS-detect (`-O`) the listening services; save all output in
   all three formats (`-oA scanname`).
5. Run safe NSE scripts only (`--script safe` or `default` minus intrusive) for banner and
   misconfiguration checks — no exploit scripts without explicit authorization.
6. Correlate results: flag unexpected open ports (database ports on web servers, management
   interfaces on user VLANs) as findings.
7. Deliver the scan report with the exact commands, timestamps, and rate used, so the blue
   team can match it against their IDS alerts.

## Expected outputs

- Host/port/service inventory in machine-readable (XML/grepable) and human-readable
  formats.
- Anomaly list: unexpected open ports and services per host.
- Scan telemetry summary (packets, duration, rate) for blue-team detection matching.

## Pitfalls

- Full-speed scans against fragile or OT networks — always start slow and honor the
  exclusion list.
- Forgetting UDP: DNS, SNMP, and VPN services hide there and are frequently the way in.
- Leaving default NSE scripts that are intrusive; audit the script set before running.

## References

- MITRE ATT&CK: Network Service Discovery (T1046), Remote System Discovery (T1018).
- Nmap documentation: timing templates and scan types.

## Blue-team control under test

This playbook validates their IDS/IPS should have fired on the scan itself — the scan
report doubles as a detection-validation artifact for their network monitoring. Paired
blue-team counterpart: `cyber_detecting_network_reconnaissance_and_port_scanning`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
