---
skill_id: red_cloud_asset_discovery
name: Cloud Asset Discovery
description: Discover a target's cloud assets — storage buckets, apps, functions, and APIs — from public sources and naming conventions.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, reconnaissance, cloud]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_cloud_storage_access_patterns
---
# Cloud Asset Discovery

## Purpose

Organizations lose track of cloud assets faster than any other infrastructure. This
playbook discovers S3 buckets, Azure blobs, GCP buckets, cloud apps, and serverless
endpoints belonging to the target using naming conventions, certificate logs, and public
enumeration — without touching the target's own accounts.

## When to use

- When the target is known to be cloud-heavy (job postings, tech stack say
  AWS/Azure/GCP).
- To find misconfigured storage and exposed cloud apps before the application-testing
  phase.
- As input to takeover and misconfiguration testing.

## Prerequisites

- Authorization covering the target's cloud footprint; discovered assets of the same org
  are in scope.
- ROE note: only read public metadata — never attempt to write to or list private bucket
  contents beyond confirming exposure.

## Procedure

1. Generate candidate bucket/storage names from the org's domains, brands, and product
   names (permutations with dev/staging/backup suffixes).
2. Check each candidate for existence and public-listability using HEAD/GET requests;
   record which allow listing vs. which merely exist.
3. For listable buckets, inventory only the object keys (names), never download private
   content beyond a single canary file to prove exposure.
4. Mine certificate logs and passive DNS for cloud-fronted hostnames (*.cloudfront.net,
   *.azurewebsites.net, *.appspot.com) tied to the org.
5. Enumerate the org's public cloud apps: check for exposed management consoles,
   unauthenticated APIs, and serverless endpoints.
6. Classify every asset: intended-public, misconfigured, or forgotten; screenshot and
   timestamp the evidence.
7. Report misconfigurations to the blue team immediately (they are live exposures), and
   fold the asset list into the test scope.

## Expected outputs

- Cloud asset inventory with exposure classification per asset.
- Misconfigured-storage findings with timestamped evidence (reported immediately).
- Cloud app/API attack surface list for later phases.

## Pitfalls

- Downloading private data from an open bucket to 'prove' exposure — one canary file is
  enough; more is a data-handling incident.
- Bucket-name permutations can collide with unrelated third parties; verify ownership
  signals before claiming.
- Forgetting regional endpoints — a bucket may exist in a region your tool didn't check.

## References

- MITRE ATT&CK: Gather Victim Network Information — Cloud (T1590.005).
- Cloud provider docs: storage access logging and public-access blocks.

## Blue-team control under test

This playbook validates their cloud security posture management should have flagged
every misconfigured asset found — each one is a CSPM coverage gap. Paired blue-team
counterpart: `cyber_analyzing_cloud_storage_access_patterns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
