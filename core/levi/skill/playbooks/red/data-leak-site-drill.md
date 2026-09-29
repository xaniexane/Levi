---
skill_id: red_data_leak_site_drill
name: Data Leak-Site Drill
description: Drill the data-leak-site extortion scenario as a communications and legal exercise.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, impact, extortion, exercise]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_ransomware_leak_site_intelligence
---
# Data Leak-Site Drill

## Purpose

Double extortion adds a leak site to the ransom — this drill walks the team through the
scenario: canary data 'published', notification obligations, and the communications
response.

## When to use

- As a tabletop with legal, comms, and leadership.
- After exfiltration testing, using realistic scenario inputs.
- To validate breach-notification workflows.

## Prerequisites

- Exercise authorization; canary data for the scenario.
- Legal and communications participation.

## Procedure

1. Present the scenario: canary data appears on a simulated leak site.
2. Walk notification obligations: regulators, customers, timelines.
3. Test the takedown options: what can actually be done about the leak site?
4. Exercise the communications response: holding statements, customer notifications.
5. Validate the forensics question: what data was actually taken (the exfil tests inform
   this)?
6. Deliver the drill report with notification-playbook updates.

## Expected outputs

- Notification-obligation walkthrough.
- Takedown-option analysis.
- Communications-plan updates.

## Pitfalls

- Real data on a real leak site — simulated scenario only.
- Skipping the forensics input — the exfil tests determine what's actually at risk.

## References

- CISA/ FBI guidance on double-extortion ransomware.

## Blue-team control under test

This playbook validates their extortion response is drilled before it's needed —
notification readiness is the deliverable. Paired blue-team counterpart:
`cyber_analyzing_ransomware_leak_site_intelligence`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
