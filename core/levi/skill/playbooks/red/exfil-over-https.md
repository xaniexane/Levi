---
skill_id: red_exfil_over_https
name: HTTPS Exfiltration Test
description: Test HTTPS exfiltration to validate DLP, TLS inspection, and egress controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, exfiltration, https, dlp]
version: 1.0.0
team: red
tests_blue: cyber_detecting_insider_data_exfiltration_via_dlp
---
# HTTPS Exfiltration Test

## Purpose

HTTPS is the exfiltration highway — encrypted, ubiquitous, trusted. This test
exfiltrates canary data over HTTPS to trusted and untrusted destinations, validating DLP
content inspection, TLS-interception coverage, and egress allowlisting.

## When to use

- During exfiltration phases.
- To validate DLP HTTPS inspection and TLS-interception deployment.
- To test egress filtering against trusted-domain exfil.

## Prerequisites

- Authorization for exfiltration testing; canary data only.
- DLP-team coordination for the inspection check.

## Procedure

1. Exfiltrate canary-pattern data over HTTPS POST to canary destinations (trusted-domain
   and untrusted).
2. Test with and without TLS interception: what does the DLP see in each case?
3. Vary the exfil: chunked uploads, compressed archives, encrypted blobs — record per-
   variant DLP results.
4. Test exfil to cloud storage and collaboration platforms (the trusted-domain path).
5. Verify all canary data destroyed at the destination.
6. Deliver the HTTPS-exfiltration assessment with inspection-coverage recommendations.

## Expected outputs

- Per-variant DLP detection results.
- TLS-interception coverage map.
- Trusted-domain exfil findings.

## Pitfalls

- Real sensitive data — canary patterns only.
- Exfil to real external services — canary destinations only.

## References

- MITRE ATT&CK: Exfiltration Over Web Service (T1567).

## Blue-team control under test

This playbook validates their DLP's HTTPS visibility is what's measured — canary
patterns leaving silently define the inspection gap. Paired blue-team counterpart:
`cyber_detecting_insider_data_exfiltration_via_dlp`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
