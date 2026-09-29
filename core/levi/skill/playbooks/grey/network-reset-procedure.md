---
skill_id: grey_network_reset_procedure
name: Exercise Network Reset Procedure
description: Reset exercise network devices and rulesets to the as-built baseline.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, resets, network, firewalls]
version: 1.0.0
team: grey
---
# Exercise Network Reset Procedure

## Purpose

Firewalls accumulate exercise rules, routes get modified, taps get moved. This procedure
resets the exercise network to its as-built baseline between iterations — rulesets,
routes, and monitoring taps.

## When to use

- Between network-focused exercise iterations.
- After firewall-rule exercises.
- When network state is suspect.

## Prerequisites

- As-built network configuration archived.
- Reset authorization.
- Exercise traffic stopped.

## Procedure

1. Confirm authorization and the device set.
2. Archive the exercised configuration (the rule changes are exercise data).
3. Restore as-built configs: firewall rulesets, routes, NAT, tap/SPAN assignments.
4. Verify the restore: path tests per the as-built test plan, tap traffic flowing.
5. Re-verify monitoring: NDR and SIEM receiving network telemetry.
6. Sign off the clean network.

## Expected outputs

- Network reset log.
- As-built verification (path tests).
- Monitoring re-verification.

## Pitfalls

- Restoring configs to the wrong devices — verify device identity.
- Lost tap/SPAN assignments — monitoring goes dark silently.
- No path tests after restore — verify the network actually works.

## References

- Network-operations literature.

## Exercise role

The network reset restores the exercise's physics — verified path by path, because the
next exercise depends on it.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
