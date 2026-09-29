---
skill_id: grey_endpoint_fleet_provisioning
name: Endpoint Fleet Provisioning
description: Provision Windows and Linux endpoint fleets with standardized baselines and agents.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, endpoints, fleet]
version: 1.0.0
team: grey
---
# Endpoint Fleet Provisioning

## Purpose

Exercises need realistic endpoint fleets: domain-joined workstations with users, EDR
agents, and logging — built identically every time. This runbook standardizes fleet
provisioning from gold images so the range is reproducible.

## When to use

- For endpoint-focused exercises (EDR validation, ransomware drills).
- When the scenario needs user-workstation realism.
- To rebuild fleets between exercise iterations.

## Prerequisites

- Gold images for each OS/persona (user workstation, server, admin jump box).
- EDR/agent installers and policies for the range.
- Domain-join automation and test-user roster.

## Procedure

1. Clone endpoints from gold images per the exercise roster (counts per persona).
2. Domain-join and place in the correct OUs; apply the range GPO baseline.
3. Install and verify EDR agents, Sysmon, and audit policies; confirm check-in to the range
   console.
4. Create test-user profiles with realistic data (canary documents, browser history) per
   the scenario.
5. Verify the logging pipeline: each endpoint's events reaching the SIEM.
6. Snapshot the fleet baseline before exercise traffic.
7. Hand over with the fleet inventory and health checklist.

## Expected outputs

- Provisioned endpoint fleet with inventory.
- Agent/logging health verification.
- Fleet baseline snapshot reference.

## Pitfalls

- Gold images with expired passwords or broken trust — validate the image before cloning
  at scale.
- EDR agents that never check in — verify, don't assume.
- Identical hostnames breaking the scenario — unique naming per the roster.

## References

- Endpoint-management documentation; EDR deployment guides.

## Exercise role

Fleet realism determines exercise realism — identical, healthy, logged endpoints are the
grey team's product.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
