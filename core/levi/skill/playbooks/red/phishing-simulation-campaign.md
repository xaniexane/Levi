---
skill_id: red_phishing_simulation_campaign
name: Phishing Simulation Campaign
description: Plan and execute an authorized phishing simulation to test user reporting, gateway filtering, and incident response.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, phishing]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_email_headers_for_phishing_investigation
---
# Phishing Simulation Campaign

## Purpose

Measure the organization's real phishing resilience: do users click, do they report,
does the gateway filter, and does the SOC respond? A well-run simulation produces click
rates, report rates, and time-to-contain metrics — the three numbers that justify the
entire awareness program.

## When to use

- As part of the social-engineering phase of an authorized assessment.
- Quarterly, to track awareness-program effectiveness over time.
- After a real phishing incident, to validate that the lessons stuck.

## Prerequisites

- Explicit social-engineering authorization: allowed techniques, target groups, and
  forbidden pretexts.
- Pre-approved email templates and landing pages; no credential harvesting beyond proof-
  of-submit.
- IT/helpdesk pre-briefed so the simulation doesn't trigger a real incident response.

## Procedure

1. Build the target list from personnel OSINT; get client sign-off on the exact recipients.
2. Register lookalike infrastructure (typosquat domain or approved sender) and warm it up
   so the test measures the gateway, not spam reputation.
3. Craft 2-3 pretext variants (IT notification, HR document, vendor invoice) with
   increasing sophistication; keep payloads inert (tracking pixel + safe link only).
4. Launch in waves, not all at once, so the SOC can demonstrate detection on wave 1 and the
   report rate on later waves is meaningful.
5. Record per-wave: delivery rate, open rate, click rate, credential-submit rate (to the
   inert form), and report rate with time-to-report.
6. For clickers, serve the approved training page immediately — the teachable moment is the
   point.
7. Debrief with the blue team: which controls fired (gateway, EDR, user reports), what the
   SOC did with the first report, and the metrics trend vs. last quarter.

## Expected outputs

- Per-wave metrics: delivered/opened/clicked/submitted/reported with timestamps.
- Control-effectiveness map: which layer caught which wave.
- Repeat-clicker list for targeted coaching (handled per the ROE privacy terms).

## Pitfalls

- Payloads that actually harvest credentials or install anything — keep everything inert
  and client-approved.
- Forgetting the helpdesk pre-brief; a good simulation looks exactly like a real
  incident to the unbriefed.
- Targeting executives or finance with wire-transfer pretexts without extra approval —
  high blast radius, needs explicit sign-off.

## References

- MITRE ATT&CK: Phishing (T1566).
- NIST SP 800-53: awareness and training controls (AT family).

## Blue-team control under test

This playbook validates their email gateway, user-reporting pipeline, and SOC triage
each get a measurable score — the report rate trend is the awareness program's KPI.
Paired blue-team counterpart:
`cyber_analyzing_email_headers_for_phishing_investigation`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
