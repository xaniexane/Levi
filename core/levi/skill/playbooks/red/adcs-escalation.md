---
skill_id: red_adcs_escalation
name: AD CS (ESC) Escalation Test
description: Test Active Directory Certificate Services misconfigurations (ESC1-ESC8) for privilege escalation.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, active-directory, adcs]
version: 1.0.0
team: red
tests_blue: cyber_exploiting_active_directory_certificate_services_esc1
---
# AD CS (ESC) Escalation Test

## Purpose

AD CS misconfigurations (the ESC family) turn certificate templates into domain-
compromise paths: enroll-as-anyone, weak EKU, NTLM relay to HTTP enrollment. This test
enumerates the CA configuration and validates each ESC primitive with proof-only
certificate operations.

## When to use

- During AD privilege-escalation phases where AD CS is deployed.
- To validate certificate-template hardening against the ESC checklist.
- When the threat model includes AD CS (most enterprises have it).

## Prerequisites

- Authorization for the AD environment including the CA infrastructure.
- Proof-only goals: enroll test certificates, never use them beyond verification.

## Procedure

1. Enumerate CAs, templates, and permissions with authorized tooling (Certify/Impacket-
   style).
2. Check each ESC primitive: ESC1 (enroll-as-anyone + client auth EKU), ESC2/3 (weak
   EKU/permissions), ESC4 (template write), ESC6 (EDITF_ATTRIBUTESUBJECTALTNAME2), ESC8
   (HTTP relay).
3. For each vulnerable template, perform a proof enrollment for a canary identity — stop at
   issuance.
4. Record whether certificate-services auditing logged the enumeration and enrollments.
5. Deliver per-template findings with the exact hardening change (permissions, EKU, flags).
6. Re-test after remediation to confirm each ESC path is closed.

## Expected outputs

- CA/template enumeration with ESC mapping.
- Proof-enrollment evidence per vulnerable template.
- Remediation verification (re-test).

## Pitfalls

- Using issued certificates for actual authentication beyond proof — stop at issuance.
- Missing ESC6/ESC8 which live in CA configuration, not templates.
- Forgetting to check enrollment permissions for low-privileged groups — that's where
  ESC1 hides.

## References

- MITRE ATT&CK: Valid Accounts via certificates; SpecterOps Certified Pre-Owned research
  (public).

## Blue-team control under test

This playbook validates their AD CS hardening gets an ESC-by-ESC verdict — each
vulnerable template is a high-severity finding with a documented fix. Paired blue-team
counterpart: `cyber_exploiting_active_directory_certificate_services_esc1`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
