---
skill_id: red_spear_phishing_attachment
name: Spear-Phishing Attachment Test
description: Test email gateway and endpoint controls against weaponized-document simulations using inert payloads.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, phishing, malware]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_email_headers_for_phishing_investigation
---
# Spear-Phishing Attachment Test

## Purpose

Determine whether malicious-document simulations reach inboxes and what happens when
opened: does the gateway detonate or strip the attachment, does EDR block the macro,
does the user enable content? All payloads are inert — the test measures controls, not
exploitation.

## When to use

- To validate email-gateway sandboxing and attachment-stripping policies.
- To test EDR behavior against macro and script execution in documents.
- When the threat model includes document-borne initial access.

## Prerequisites

- Authorization for attachment-based testing; payloads reviewed and approved as inert.
- EDR/gateway teams aware of the test window to distinguish it from real malware.

## Procedure

1. Build inert document payloads: macros that write a canary registry key or beacon to a
   controlled listener, never a real implant.
2. Send through the normal mail flow (not whitelisted) so the gateway is genuinely tested —
   coordinate the window with the SOC.
3. Test the matrix: Office macro documents, PDFs with embedded scripts, archives (zip/iso)
   with script payloads, OneNote-style lures where in scope.
4. Record per-sample: gateway verdict (delivered/quarantined/stripped), EDR verdict on
   open, and whether macros were auto-blocked or user-enabled.
5. For delivered samples, measure whether the inert beacon fired — proving code execution
   would have occurred.
6. Map each result to the control that should have caught it and note the gap.

## Expected outputs

- Per-sample control matrix: gateway verdict × EDR verdict × execution result.
- Inert-beacon evidence proving which samples would have executed.
- Control-gap list with recommended policy changes.

## Pitfalls

- Real payloads 'for realism' — never; inert beacons prove the same point with zero
  risk.
- Whitelisting the sender to 'make sure it arrives' — that defeats the gateway test
  entirely.
- Testing file types the org has legitimately blocked (e.g., ISOs) without noting the
  block is the expected pass.

## References

- MITRE ATT&CK: Phishing — Spearphishing Attachment (T1566.001).

## Blue-team control under test

This playbook validates their gateway sandboxing and EDR macro policies get a per-sample
scorecard — every delivered-and-executed sample is a control failure to fix. Paired
blue-team counterpart: `cyber_analyzing_email_headers_for_phishing_investigation`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
