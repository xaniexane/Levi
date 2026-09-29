---
skill_id: grey_red_team_infrastructure_setup
name: Red Team Infrastructure Setup
description: Set up red-team attack infrastructure: C2, phishing, and tooling hosts.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, red-team, infrastructure]
version: 1.0.0
team: grey
---
# Red Team Infrastructure Setup

## Purpose

The red team needs its own infrastructure: C2 servers, phishing domains, payload
hosting, tooling — built by the grey team to keep it contained, logged, and separate
from real attacker infrastructure. This setup builds it.

## When to use

- Before red-team execution phases.
- For phishing scenarios needing mail infrastructure.

## Prerequisites

- ROE authorizing the red infrastructure.
- Isolated red-team network segment.
- Canary domains and certificates.

## Procedure

1. Deploy the red-team segment: attack hosts, C2 servers (canary), payload staging.
2. Set up phishing infrastructure: canary domains, mail relay, landing pages — all clearly
   labeled.
3. Configure egress from the red segment through grey-team monitoring (all red traffic
   logged).
4. Issue the red team their access: VPN/jump credentials, tooling, the ROE boundaries.
5. Verify containment: red infrastructure can't reach production or the real internet
   beyond the simulator.
6. Hand over with the infrastructure inventory and monitoring confirmation.

## Expected outputs

- Red-team infrastructure inventory.
- Egress-monitoring verification.
- Containment verification.

## Pitfalls

- Red infrastructure with real internet egress — contain it.
- Phishing domains that could confuse real users — canary naming, limited scope.
- Unlogged red traffic — the grey team monitors its own red segment.

## References

- Red-team infrastructure literature (public).

## Exercise role

Red-team infrastructure is a stage weapon — functional, contained, monitored, and
unmistakably exercise-owned.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
