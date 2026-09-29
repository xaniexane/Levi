---
skill_id: red_cloud_api_c2_test
name: Cloud API C2 Test
description: Test cloud-API-based C2 (dead drops, tasking via cloud services) to validate cloud monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, cloud, c2]
version: 1.0.0
team: red
tests_blue: cyber_core_c2_beaconing
---
# Cloud API C2 Test

## Purpose

Cloud APIs make excellent C2: the traffic is legitimate TLS to trusted domains. This
test builds canary dead-drop tasking over cloud storage/APIs and validates whether cloud
audit logging and CASB distinguish C2 use from normal use.

## When to use

- During cloud C2 phases.
- To validate cloud audit-log alerting on anomalous API use.
- To test the trusted-domain blind spot in web filtering.

## Prerequisites

- Authorization for the cloud tenants; canary storage/identities.
- CASB/cloud-admin coordination.

## Procedure

1. Build canary tasking: beacon writes a canary file, controller reads it, replies via
   another object.
2. Vary the pattern: polling intervals, object naming, data encoding.
3. Check cloud audit logs: is the anomalous API pattern visible and alerted?
4. Test CASB: does it distinguish the canary C2 from normal storage use?
5. Tear down all canary objects and identities.
6. Deliver the cloud-API C2 assessment.

## Expected outputs

- Cloud-API C2 detection results.
- Audit-log visibility assessment.
- CASB findings.

## Pitfalls

- Real cloud identities for the C2 — canary identities only.
- Leaving canary objects in production buckets — verify deletion.

## References

- MITRE ATT&CK: Application Layer Protocol — cloud API abuse literature.

## Blue-team control under test

This playbook validates their cloud monitoring faces trusted-domain C2 — API patterns
nobody flagged are the cloud-detection gap. Paired blue-team counterpart:
`cyber_core_c2_beaconing`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
