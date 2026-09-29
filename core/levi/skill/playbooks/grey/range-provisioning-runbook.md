---
skill_id: grey_range_provisioning_runbook
name: Range Provisioning Runbook
description: Provision isolated exercise ranges on demand with network, identity, and logging baselines.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, range, infrastructure]
version: 1.0.0
team: grey
---
# Range Provisioning Runbook

## Purpose

Every exercise starts with a range: isolated networks, domain infrastructure, logging
pipelines, and target estates. This runbook standardizes provisioning so ranges are
reproducible, isolated from production, and instrumented before the first red action.

## When to use

- Before any red-team exercise or cyber range event.
- When standing up persistent training ranges.
- To rebuild a range after a destructive exercise.

## Prerequisites

- Virtualization or cloud capacity allocated to the range program.
- Network isolation design approved (no production routes).
- License inventory for OS and tooling.

## Procedure

1. Allocate the range network segments per the exercise design (red, blue, grey, target
   VLANs/VPCs).
2. Deploy identity infrastructure: lab domain controllers, test users, service accounts —
   all clearly labeled.
3. Deploy logging: SIEM forwarder, Sysmon configs, audit policies on every host before any
   exercise traffic.
4. Deploy the target estate: workstations, servers, and services matching the exercise
   scenario.
5. Verify isolation: no routes to production, DNS contained, egress controlled and logged.
6. Snapshot the pristine range state (see the snapshot playbooks) before handover.
7. Hand over to the exercise director with the range-readiness checklist signed.

## Expected outputs

- Provisioned range with network map.
- Isolation-verification evidence.
- Pristine-state snapshot reference.
- Range-readiness checklist.

## Pitfalls

- Provisioning without the logging baseline — exercise traffic without telemetry is
  wasted.
- DNS or routes leaking to production — verify isolation actively, don't assume.
- Skipping the pristine snapshot — you can't reset what you never captured.

## References

- NIST SP 800-115 (testing guidance); range-operations literature.

## Exercise role

This is the foundation every exercise stands on — a range provisioned without isolation
verification or logging baselines invalidates everything built on it.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
