---
skill_id: red_ad_replication_abuse
name: AD Replication Abuse Test
description: Test malicious DC promotion and replication abuse to validate DC-security monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, lateral-movement, active-directory, replication]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_active_directory_acl_abuse
---
# AD Replication Abuse Test

## Purpose

Rogue DC promotion (DCShadow) and replication abuse give attackers directory-write
primitives. This lab test validates DC-promotion monitoring and that replication-based
attacks are detectable — without endangering production AD.

## When to use

- Lab-only, during advanced AD phases.
- To validate monitoring for unauthorized DC promotions.
- To test SIEM rules for replication anomalies.

## Prerequisites

- Isolated lab forest; explicit authorization for DC-promotion techniques.
- Never against production AD.

## Procedure

1. In the lab, register a rogue DC (DCShadow-style) and push a canary directory change.
2. Record telemetry: DC-promotion events, replication anomalies, and SIEM alerts.
3. Test the reverse: unauthorized replication-partner additions.
4. Verify the lab forest is clean afterward (metadata cleanup of the rogue DC).
5. Deliver the DC-security monitoring assessment with promotion-alerting recommendations.

## Expected outputs

- Rogue-DC telemetry record.
- Replication-anomaly detection results.
- Lab cleanup verification.

## Pitfalls

- Any production AD contact — lab only, enforced.
- Leaving rogue-DC metadata in the lab forest — clean it.
- Confusing lab replication with the DCSync test — related but distinct techniques.

## References

- MITRE ATT&CK: Domain Controller artifacts; public DCShadow research.

## Blue-team control under test

This playbook validates their DC-promotion monitoring is under test — an unalerted rogue
DC is a forest-security failure. Paired blue-team counterpart:
`cyber_analyzing_active_directory_acl_abuse`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
