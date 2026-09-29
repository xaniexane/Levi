---
skill_id: red_cloud_storage_collection
name: Cloud Storage Collection Test
description: Test cloud-storage enumeration and collection to validate CASB and DLP coverage.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, collection, cloud, dlp]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_cloud_storage_access_patterns
---
# Cloud Storage Collection Test

## Purpose

Cloud storage — drives, buckets, SharePoint — is where the data actually lives now. This
test enumerates and samples cloud storage with read-only roles, validating CASB
visibility, sharing-link governance, and cloud DLP.

## When to use

- During cloud collection phases.
- To validate CASB discovery and cloud DLP policies.
- To audit sharing-link exposure.

## Prerequisites

- Authorization for the cloud tenants; read-only test roles.
- Canary files planted for DLP validation.

## Procedure

1. Enumerate cloud storage: drives, buckets, SharePoint sites visible to the test role.
2. Audit sharing links: anyone-with-link exposures of canary and real sensitive locations
   (counts, not content).
3. Test the canary DLP: do canary-pattern files trigger cloud DLP policies?
4. Sample access logging: is storage access logged and is the test enumeration visible?
5. Deliver the cloud-storage exposure and DLP assessment.

## Expected outputs

- Cloud-storage inventory with exposure analysis.
- Sharing-link audit results.
- Cloud DLP canary results.

## Pitfalls

- Downloading real sensitive data — enumerate metadata, sample canaries.
- Testing sharing links by accessing them externally without approval — audit, don't
  exploit.

## References

- MITRE ATT&CK: Cloud Storage Object Discovery; CSA guidance.

## Blue-team control under test

This playbook validates their CASB and cloud DLP are under test — anyone-with-link
exposures are the cloud sharing finding. Paired blue-team counterpart:
`cyber_analyzing_cloud_storage_access_patterns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
