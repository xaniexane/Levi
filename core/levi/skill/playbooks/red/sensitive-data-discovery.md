---
skill_id: red_sensitive_data_discovery
name: Sensitive Data Discovery Test
description: Discover sensitive-data exposure across shares, endpoints, and repos to validate DLP.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, dlp, data]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# Sensitive Data Discovery Test

## Purpose

Attackers hunt data; this test hunts it first — with rules. Canary-pattern scanning
across shares, endpoints, and repos validates DLP coverage, data classification, and
whether sensitive data lives where it shouldn't.

## When to use

- During discovery phases, as the data-risk complement to share enumeration.
- To validate DLP rule coverage with canary patterns.
- Before collection/exfiltration phases, to scope what's actually exposed.

## Prerequisites

- Authorization with agreed data patterns (canary + pattern types, not real PII
  harvesting).
- Sampling depth agreed; DLP team coordination.

## Procedure

1. Deploy canary files with known patterns (fake PANs, fake SSNs, canary tokens) across
   shares and endpoints.
2. Scan the agreed scope for the canary patterns and for real sensitive patterns (counts
   and locations, not exfiltration).
3. Check whether DLP flagged the canary files — per location and per pattern type.
4. Sample repositories and wikis for secrets (canary tokens planted; real secrets reported
   as counts).
5. Deliver the data-exposure map with DLP-tuning and classification recommendations.

## Expected outputs

- Canary-pattern detection results per location.
- Sensitive-data exposure map (counts and locations).
- DLP coverage gaps with tuning recommendations.

## Pitfalls

- Exfiltrating real sensitive data 'for proof' — counts and locations, never content.
- Scanning outside the agreed scope — HR, legal, and exec shares need specific approval.
- Forgetting that the scan itself must be logged — coordinate with the DLP team.

## References

- MITRE ATT&CK: Data Discovery; NIST SP 800-60 (data categorization).

## Blue-team control under test

This playbook validates their DLP and data classification are under test — canary
patterns the DLP misses are coverage gaps with locations attached. Paired blue-team
counterpart: `cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
