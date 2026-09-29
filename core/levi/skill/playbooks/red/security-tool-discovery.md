---
skill_id: red_security_tool_discovery
name: Security Tool Discovery Test
description: Test security-tooling enumeration to validate tamper protection and deception.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, edr, deception]
version: 1.0.0
team: red
tests_blue: cyber_core_ad_acl_abuse
---
# Security Tool Discovery Test

## Purpose

Attackers enumerate defenses before evading them. This test performs standard security-
tooling discovery — installed EDR, AV, logging agents — and validates tamper protection,
uninstallation controls, and whether discovery of defenses is itself detected.

## When to use

- Early in engagements, mirroring attacker reconnaissance.
- To validate EDR tamper protection and uninstall passwords.
- To test whether defense-discovery triggers any alert.

## Prerequisites

- Authorization for the test hosts; read-only enumeration.

## Procedure

1. Enumerate installed security products via standard paths (WMI, registry, services,
   processes).
2. Check tamper protection: can the test context disable or uninstall the agent (attempt
   the control, don't succeed without approval)?
3. Record whether the enumeration itself generated any telemetry.
4. Test the EDR's self-defense: service stop attempts, driver unload attempts (blocked
   expected).
5. Deliver the defense-visibility assessment with tamper-protection recommendations.

## Expected outputs

- Security-product inventory per host.
- Tamper-protection test results.
- Defense-discovery telemetry assessment.

## Pitfalls

- Actually disabling protection without approval — attempt-to-control tests need
  explicit scope.
- Uninstalling agents even temporarily — that's an availability impact.

## References

- MITRE ATT&CK: Security Software Discovery (T1518.001).

## Blue-team control under test

This playbook validates their defense tamper protection is under test — an EDR the test
user can disable is a control failure, not a finding to note politely. Paired blue-team
counterpart: `cyber_core_ad_acl_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
