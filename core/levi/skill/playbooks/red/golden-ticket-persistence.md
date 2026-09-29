---
skill_id: red_golden_ticket_persistence
name: Golden Ticket Persistence Test
description: Test Kerberos golden-ticket forgery in a lab to validate KRBTGT rotation and ticket monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, persistence, kerberos, active-directory, lab]
version: 1.0.0
team: red
tests_blue: cyber_detecting_golden_ticket_attacks_in_kerberos_logs
---
# Golden Ticket Persistence Test

## Purpose

A golden ticket — a forged Kerberos TGT signed with the KRBTGT hash — persists until the
KRBTGT password is rotated twice, surviving password changes. This lab test validates
KRBTGT rotation hygiene and ticket-anomaly monitoring without endangering a production
domain.

## When to use

- Lab-only, during AD persistence phases.
- To validate KRBTGT rotation policy (twice, with replication wait).
- To test SIEM rules for ticket anomalies (lifetime, encryption type).

## Prerequisites

- Isolated lab domain; never a production AD.
- KRBTGT hash obtained in the lab under authorization.

## Procedure

1. Extract the KRBTGT hash in the lab domain using authorized tooling.
2. Forge a golden ticket with an anomalous lifetime (e.g., 10 years) for a test account.
3. Use the ticket to access a lab resource; record success.
4. Check blue-team detection: ticket-lifetime anomalies, RC4 vs. AES encryption downgrades,
   and logon without prior AS-REQ.
5. Rotate the KRBTGT password twice (with replication wait) and verify the forged ticket
   stops working.
6. Deliver the KRBTGT-hygiene assessment with rotation runbook recommendations.

## Expected outputs

- Forged-ticket usage evidence with anomaly markers.
- Detection assessment per anomaly type.
- KRBTGT double-rotation verification.

## Pitfalls

- Any contact with production AD — lab only, no exceptions.
- Single KRBTGT rotation presented as remediation — it must be twice.
- Forgetting that golden tickets bypass smart-card requirements — note the implication.

## References

- MITRE ATT&CK: Steal or Forge Kerberos Tickets — Golden Ticket (T1558.001).
- Microsoft: KRBTGT reset guidance.

## Blue-team control under test

This playbook validates their KRBTGT rotation hygiene and Kerberos anomaly monitoring
are under test — unalerted decade-long tickets are an AD-monitoring failure. Paired
blue-team counterpart: `cyber_detecting_golden_ticket_attacks_in_kerberos_logs`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
