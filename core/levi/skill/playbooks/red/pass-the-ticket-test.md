---
skill_id: red_pass_the_ticket_test
name: Pass-the-Ticket Test
description: Test pass-the-ticket lateral movement to validate Kerberos monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, kerberos, pass-the-ticket]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_rdp
---
# Pass-the-Ticket Test

## Purpose

Pass-the-ticket replays stolen Kerberos tickets for lateral movement that looks like
normal Kerberos. This test validates whether ticket replay — especially across hosts —
is distinguishable in the monitoring.

## When to use

- During lateral-movement phases in AD environments.
- To validate Kerberos service-ticket monitoring.
- Paired with the overpass-the-hash test for the full ticket-attack picture.

## Prerequisites

- Authorization for ticket operations; ticket material handled per the ROE.
- Canary service tickets where possible.

## Procedure

1. Export a canary service ticket from the source context (authorized).
2. Inject the ticket into a fresh logon session on the test host and access the target
   resource.
3. Record telemetry: 4624/4634 pairs, Kerberos service-ticket events, EDR alerts.
4. Test cross-host replay: does the ticket work from an unexpected host, and does anything
   flag it?
5. Test the overpass-the-hash variant (NTLM hash → Kerberos tickets) as a separate case.
6. Destroy all ticket material; verify no test tickets remain valid.
7. Deliver the ticket-replay assessment with Kerberos-monitoring recommendations.

## Expected outputs

- Ticket-replay telemetry record.
- Cross-host replay detection results.
- Overpass-the-hash comparison.

## Pitfalls

- Ticket material lingering — destroy per the ROE.
- Real user TGTs without approval — canary tickets first.
- Forgetting that ticket lifetime bounds the test window — plan accordingly.

## References

- MITRE ATT&CK: Use Alternate Authentication Material — Pass the Ticket (T1550.003).

## Blue-team control under test

This playbook validates their Kerberos monitoring is under test — ticket replay that
looks like normal auth is the detection challenge to solve. Paired blue-team
counterpart:
`cyber_core_lateral_movement_rdp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
