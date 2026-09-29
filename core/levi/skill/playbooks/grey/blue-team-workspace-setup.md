---
skill_id: grey_blue_team_workspace_setup
name: Blue Team Workspace Setup
description: Set up the blue-team defense workspace: SIEM views, comms, and playbooks.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, blue-team, workspace]
version: 1.0.0
team: grey
---
# Blue Team Workspace Setup

## Purpose

The blue team needs their battle station: SIEM access with exercise views, communication
channels, IR playbooks, and the escalation paths. This setup builds it before the first
alert.

## When to use

- Before blue-team execution phases.
- For SOC-validation exercises.

## Prerequisites

- Blue-team roster and roles.
- SIEM exercise workspace from the logging pipeline.

## Procedure

1. Provision SIEM access with exercise-specific views, dashboards, and saved searches.
2. Set up communication channels: incident channel, escalation contacts, bridge details.
3. Load the IR playbooks being tested and the exercise's inject schedule (sealed until
   execution).
4. Configure alerting: exercise alerts routed to the blue team, tuned per the scenario.
5. Verify the blue team can see the range telemetry but not the red team's plans (access-
   control check).
6. Hand over with the workspace guide and comms plan.

## Expected outputs

- Blue-team workspace with views and dashboards.
- Communications plan.
- Access-control verification.

## Pitfalls

- Blue team with red-team visibility (or vice versa) — verify the access split.
- Missing comms plan — the first incident without a bridge is chaos.
- Playbooks loaded but untested — walk one before execution.

## References

- Incident-response literature; SOC operations guides.

## Exercise role

The blue team's workspace is their instrument panel — built and verified before the
first alert, not during it.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
