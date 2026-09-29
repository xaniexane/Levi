---
skill_id: red_qr_code_phishing
name: QR Code Phishing Test
description: Test user and gateway behavior with QR-code lures that bypass text-based email filtering.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, initial-access, phishing, qr-code]
version: 1.0.0
team: red
tests_blue: cyber_detecting_qr_code_phishing_with_email_security
---
# QR Code Phishing Test

## Purpose

QR codes smuggle URLs past text-based email filters and push victims to mobile browsers
where corporate controls are thinner. This test measures whether QR lures reach inboxes,
get scanned, and what the mobile-side controls do about it.

## When to use

- As a phishing-campaign variant when text-based lures are well-defended.
- To test mobile device management and mobile browser protections.
- When the threat model includes QR-based phishing (quishing).

## Prerequisites

- Same social-engineering authorization as the phishing campaign; QR lures are a
  variant, not a separate free pass.
- Inert landing pages only; no credential harvesting beyond proof-of-visit.

## Procedure

1. Generate QR codes encoding the inert landing-page URL; embed them in approved email
   templates (fake MFA enrollment, package delivery).
2. Send through the normal mail flow and record gateway verdicts — do image-based lures
   bypass the text filters?
3. Track scans: QR scan events, device type (mobile vs. desktop), and landing-page visits.
4. Measure mobile-side controls: MDM browser policy, safe-browsing on mobile, and whether
   the corporate VPN/proxy inspects the visit.
5. Compare QR-lure metrics against the text-lure baseline from the main phishing campaign.
6. Debrief with awareness-training input: QR lures need their own training module.

## Expected outputs

- QR-lure delivery/scan/visit funnel vs. text-lure baseline.
- Gateway image-analysis verdicts.
- Mobile-control assessment for QR-driven visits.

## Pitfalls

- Assuming desktop email clients render QR codes usefully — most scans happen on phones;
  design for that.
- Real credential harvesting on the landing page — inert proof-of-visit only.
- Forgetting accessibility: some users can't scan QR codes; the test measures those who
  can.

## References

- MITRE ATT&CK: Phishing — Spearphishing Link (T1566.002).
- Industry reporting on QR-code phishing trends (public).

## Blue-team control under test

This playbook validates their email gateway's image analysis and mobile-device controls
are the layers under test — QR lures that sail through both are a filtering gap. Paired
blue-team counterpart: `cyber_detecting_qr_code_phishing_with_email_security`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
