---
skill_id: grey_endpoint_reimage_reset
name: Endpoint Reimage Reset
description: Reimage exercise endpoints to gold images between phases.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, resets, endpoints, reimage]
version: 1.0.0
team: grey
---
# Endpoint Reimage Reset

## Purpose

Endpoints accumulate exercise artifacts fast — malware, persistence, config drift. This
reimage reset returns endpoints to gold images between phases: fast, complete, and the
standard hygiene between red and blue turns.

## When to use

- Between exercise phases.
- After endpoint-compromise scenarios.
- When endpoint state is suspect.

## Prerequisites

- Gold images current and verified.
- Endpoint data to preserve identified (usually none — endpoints are cattle).
- Reset authorization for the endpoint set.

## Procedure

1. Confirm the endpoint set and the gold-image version.
2. Capture any required state (usually just the inventory — endpoints hold no exercise
   record).
3. Reimage from gold: PXE, template redeploy, or cloud re-provision per the platform.
4. Re-verify post-image: domain join, EDR check-in, logging flow, baseline snapshot.
5. Return endpoints to the exercise pool with the health checklist.
6. Log the reimage batch with timestamps.

## Expected outputs

- Reimage batch log.
- Post-image health verification.
- Returned-to-pool inventory.

## Pitfalls

- Reimaging the wrong endpoints — confirm the set, especially with similar hostnames.
- Stale gold images — the image must include current agents and patches for the
  scenario.
- Skipping post-image verification — a reimaged endpoint with no logging is a blind
  host.

## References

- Endpoint-management literature.

## Exercise role

Endpoints are cattle in the exercise — reimaged between phases without sentiment,
verified before return.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
