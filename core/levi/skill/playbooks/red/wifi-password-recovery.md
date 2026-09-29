---
skill_id: red_wifi_password_recovery
name: Wi-Fi Password Recovery Test
description: Test wireless profile and credential recovery to validate wireless security posture.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, credential-access, wifi, wireless]
version: 1.0.0
team: red
tests_blue: cyber_performing_wireless_security_assessment_with_kismet
---
# Wi-Fi Password Recovery Test

## Purpose

Windows stores wireless profiles with recoverable keys; `netsh wlan show profiles` with
key=clear is a built-in credential disclosure. This test validates what wireless
material is recoverable and whether PSK hygiene and certificate-based auth are in place.

## When to use

- During credential-access phases on laptops.
- To validate the move from PSK to certificate-based wireless auth.
- As a quick win during workstation assessments.

## Prerequisites

- Authorization for the test laptops; user-context access.

## Procedure

1. Enumerate wireless profiles on test laptops; export keys for canary SSIDs.
2. Assess: are production SSIDs using PSKs recoverable by any user-context process?
3. Check for certificate-based (EAP-TLS) vs. PSK deployments across the sampled fleet.
4. Record whether profile enumeration tripped any monitoring (it usually doesn't — note
   that).
5. Deliver the wireless-auth assessment with EAP-TLS migration recommendations.

## Expected outputs

- Wireless-profile recovery results per laptop.
- PSK vs. certificate-auth deployment map.
- Migration recommendations.

## Pitfalls

- Recovering real production PSKs — report existence and scope, handle values per the
  ROE.
- Assuming 'it usually doesn't alert' without testing — run the canary and check.

## References

- MITRE ATT&CK: Credentials from Password Stores; netsh wlan documentation.

## Blue-team control under test

This playbook validates their wireless-auth architecture is under test — user-
recoverable production PSKs are a migration-to-EAP-TLS finding. Paired blue-team
counterpart: `cyber_performing_wireless_security_assessment_with_kismet`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
