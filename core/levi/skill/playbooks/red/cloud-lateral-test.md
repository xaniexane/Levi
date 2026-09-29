---
skill_id: red_cloud_lateral_test
name: Cloud Lateral Movement Test
description: Test cloud role-assumption and lateral movement to validate CloudTrail and permission boundaries.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, cloud, iam]
version: 1.0.0
team: red
tests_blue: cyber_core_lateral_movement_rdp
---
# Cloud Lateral Movement Test

## Purpose

In cloud, lateral movement is role assumption and permission pivoting — no SMB needed.
This test chains assumable roles and cross-account trust with a low-privilege start,
validating permission boundaries and CloudTrail alerting on anomalous role use.

## When to use

- During cloud phases.
- To validate IAM permission boundaries and trust policies.
- To test CloudTrail alerting on role-assumption anomalies.

## Prerequisites

- Authorization for the cloud accounts; low-privilege test role as the start.
- Agreement on which roles may be assumed (canary roles preferred).

## Procedure

1. From the start role, enumerate assumable roles and cross-account trusts.
2. Assume roles along the authorized chain; at each step record effective permissions and
   CloudTrail events.
3. Test for confused-deputy and external-ID weaknesses in trust policies (proof-only).
4. Attempt the canary objective (read a canary-flagged resource) via the role chain.
5. Record whether anomalous role assumption alerted.
6. Deliver the cloud permission-boundary assessment with trust-policy fixes.

## Expected outputs

- Role-assumption chain with per-step permissions.
- CloudTrail anomaly-alerting results.
- Trust-policy findings.

## Pitfalls

- Assuming roles outside the agreed chain — scope strictly.
- Exploiting confused-deputy beyond proof — note, don't exploit.
- Forgetting that CloudTrail must be enabled in all regions — verify.

## References

- MITRE ATT&CK: Valid Accounts — Cloud Accounts (T1078.004).

## Blue-team control under test

This playbook validates their cloud permission boundaries are under test — role chains
that reach further than intended are IAM findings. Paired blue-team counterpart:
`cyber_core_lateral_movement_rdp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
