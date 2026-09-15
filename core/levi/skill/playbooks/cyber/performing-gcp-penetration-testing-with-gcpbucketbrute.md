---
skill_id: cyber_performing_gcp_penetration_testing_with_gcpbucketbrute
name: GCP Bucket Enumeration Defense
description: Detect and remediate exposed GCP storage buckets that enumeration tools target.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, gcp, detection]
version: 1.0.0
---
# GCP Bucket Enumeration Defense

## Purpose

Tools that brute-force GCP storage bucket names exploit one fact:
predictable bucket names plus misconfigured IAM equals public data.
Rather than teaching enumeration, this playbook takes the defender's
view: how to find your own exposed buckets, detect enumeration attempts,
and harden storage so brute-forcing finds nothing.

## When to use

- Auditing GCP storage for public or over-permissive buckets.
- Responding to a report that a bucket was found externally.
- Detecting bucket-name enumeration campaigns in Cloud Audit Logs.
- Pre-launch review of any new storage bucket.

## Prerequisites

- GCP IAM rights to list buckets and read IAM policies across the
  audited projects (Security Reviewer or equivalent).
- Access to Cloud Audit Logs (Admin Activity and Data Access) in the
  SIEM or Log Explorer.
- An inventory of which buckets are intended to be public, so the
  audit has a baseline.

## Procedure

1. Inventory all buckets: `gcloud storage ls` across projects, then
   pull each bucket's IAM policy and uniform bucket-level access
   settings.
2. Flag exposure: any binding granting `allUsers` or
   `allAuthenticatedUsers` roles like `roles/storage.objectViewer` —
   `allAuthenticatedUsers` means any Google account, not your org.
3. Check Organization Policy constraints: enforce
   `constraints/storage.publicAccessPrevention` at the org or folder
   level so new buckets cannot go public by accident.
4. Verify no sensitive data is reachable: sample-list objects in
   flagged buckets and check for PII, keys, backups, or customer data.
5. Hunt for enumeration in logs: spikes of 404/403 responses on
   `storage.googleapis.com`, especially XML API `ListBucket` attempts
   from single IPs or with sequential name patterns — a sign someone
   is brute-forcing names.
6. Detect IAM probing: `storage.buckets.getIamPolicy` and
   `storage.buckets.testIamPermissions` calls from unfamiliar
   principals often precede exploitation.
7. Remediate: remove public bindings, enable uniform bucket-level
   access, rotate any credentials found in exposed objects, and apply
   VPC Service Controls for sensitive projects.
8. Prevent recurrence: add bucket-publicity checks to CI/CD and
   deployment reviews; alert on any future `allUsers` binding via a
   log-based alert.

## Expected outputs

- A bucket inventory with exposure classification per bucket.
- Remediation records: bindings removed, policies enforced.
- Detection rules for enumeration and IAM-probing patterns.
- A preventive control: org policy plus CI/CD check.

## Pitfalls

- Confusing `allAuthenticatedUsers` with "my organization": it is every
  Google account on Earth.
- Remediating the binding but leaving exposed credentials unrotated.
- Checking only one project when enumeration targets the whole org.
- Alerting on enumeration without blocking: pair detection with the
  org-level public-access prevention.

## References

- Google Cloud documentation: Cloud Storage IAM and public access prevention
- Google Cloud documentation: VPC Service Controls
- MITRE ATT&CK: Cloud Storage Object discovery (T1619)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
