---
skill_id: red_cloud_discovery_test
name: Cloud Resource Discovery Test
description: Test cloud resource and permission enumeration to validate cloud audit logging.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, cloud, iam]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_cloud_storage_access_patterns
---
# Cloud Resource Discovery Test

## Purpose

Cloud consoles and APIs expose the whole estate to anyone with read rights — often over-
broad. This test enumerates cloud resources, IAM permissions, and storage exposure with
a read-only role to validate least privilege and control-plane audit logging.

## When to use

- During cloud phases, with a low-privilege cloud role.
- To validate IAM least privilege and CloudTrail/audit-log coverage.
- To find publicly exposed storage and over-permissive roles.

## Prerequisites

- Authorization for the cloud accounts; read-only test role.
- Agreement on enumeration scope (accounts, regions).

## Procedure

1. With the read-only role, enumerate: IAM users/roles/policies, compute, storage,
   databases, network config.
2. Evaluate effective permissions: what can this 'read-only' role actually do (privilege-
   escalation paths noted, not exploited without approval)?
3. Check storage exposure: public buckets, public snapshots, open security groups.
4. Verify control-plane logging: did the enumeration appear in CloudTrail/audit logs, and
   is it alerted on?
5. Deliver the cloud-exposure map with IAM and logging recommendations.

## Expected outputs

- Cloud resource and IAM enumeration results.
- Public-exposure findings.
- Control-plane logging assessment.

## Pitfalls

- Enumerating beyond the agreed accounts/regions — scope strictly.
- Exploiting privesc paths found during enumeration without fresh approval — note, don't
  exploit.
- Forgetting multi-cloud — cover each provider in scope.

## References

- MITRE ATT&CK: Cloud Service Discovery (T1526).

## Blue-team control under test

This playbook validates their cloud IAM least privilege and audit logging are under test
— read-only roles that can enumerate everything are the norm to challenge. Paired blue-
team counterpart: `cyber_analyzing_cloud_storage_access_patterns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
