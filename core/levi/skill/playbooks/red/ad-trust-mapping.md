---
skill_id: red_ad_trust_mapping
name: AD Trust Relationship Mapping Test
description: Map AD trust relationships to validate trust-security monitoring and SID-filtering.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, active-directory, trusts]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_active_directory_acl_abuse
---
# AD Trust Relationship Mapping Test

## Purpose

Trusts extend the security boundary — a compromise in one domain flows through trusts.
This test maps all trust relationships, their direction and transitivity, and validates
SID filtering and trust monitoring.

## When to use

- During AD discovery in multi-domain forests.
- To validate trust hardening (SID filtering, selective auth).
- When the threat model includes cross-domain movement.

## Prerequisites

- Authorization for the forest; standard domain user context suffices.

## Procedure

1. Enumerate all trusts: direction, transitivity, type (forest, external, shortcut).
2. Check SID filtering and selective-authentication status per trust.
3. Map the attack paths trusts enable: which principals in trusted domains have rights
   here?
4. Test trust transitivity assumptions with canary cross-domain access (authorized).
5. Record whether cross-trust authentication is monitored.
6. Deliver the trust-security assessment with filtering recommendations.

## Expected outputs

- Trust map with direction, transitivity, and filtering status.
- Cross-trust attack-path analysis.
- Trust-monitoring findings.

## Pitfalls

- Cross-domain access testing without approval from both domain owners.
- Assuming external trusts filter SIDs by default — verify.

## References

- MITRE ATT&CK: Domain Trust Discovery (T1482).
- Microsoft: trust hardening guidance.

## Blue-team control under test

This playbook validates their trust architecture is under test — unfiltered trusts are
boundary extensions the blue team must monitor. Paired blue-team counterpart:
`cyber_analyzing_active_directory_acl_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
