---
skill_id: red_cloud_ssrf_metadata
name: Cloud SSRF to Instance Metadata Test
description: Test server-side request forgery paths to cloud instance metadata to validate SSRF defenses and IMDSv2 enforcement.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, execution, cloud, ssrf]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_cloud_storage_access_patterns
---
# Cloud SSRF to Instance Metadata Test

## Purpose

SSRF against cloud instance metadata (169.254.169.254) is the classic cloud initial-
access path to credentials. This test probes in-scope web applications for SSRF,
attempts metadata access with proof-only goals, and validates IMDSv2 enforcement — the
control that breaks this attack.

## When to use

- During web application testing of cloud-hosted apps.
- To validate IMDSv2 enforcement across the cloud fleet.
- When the threat model includes cloud credential theft via application flaws.

## Prerequisites

- Explicit authorization for SSRF testing; some ROEs restrict metadata-access attempts —
  confirm first.
- Cloud environment in scope with IMDS configuration documented.

## Procedure

1. Identify SSRF-prone parameters in the target app: URL fetchers, webhooks, file-import
   features, PDF generators.
2. Probe with canary callbacks to a controlled listener to confirm outbound request
   capability without touching metadata.
3. Where authorized, attempt metadata access: IMDSv1 (no token) vs. IMDSv2 (token required)
   — record which the instance enforces.
4. Proof goal only: read the instance identity document, never credentials; credential
   access needs separate authorization.
5. Check for credential exfiltration paths: would retrieved credentials reach the internet
   (egress filtering)?
6. Deliver the SSRF findings with IMDSv2-enforcement recommendations per instance fleet.

## Expected outputs

- SSRF probe results per parameter with canary-callback evidence.
- IMDSv1 vs. IMDSv2 enforcement assessment.
- Egress-filtering observations.

## Pitfalls

- Pulling real instance credentials 'to prove impact' — the identity document proves the
  path; credentials need separate approval.
- SSRF probes that hit internal services beyond metadata — constrain targets per the
  ROE.
- Forgetting containers/VMs have their own metadata endpoints with different
  protections.

## References

- MITRE ATT&CK: Server-Side Request Forgery; Cloud Instance Metadata API (T1552.005).
- Cloud provider IMDSv2 enforcement documentation.

## Blue-team control under test

This playbook validates their IMDSv2 rollout and SSRF input validation are under test —
IMDSv1 instances reachable via SSRF are critical cloud-hygiene findings. Paired blue-
team counterpart: `cyber_analyzing_cloud_storage_access_patterns`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
