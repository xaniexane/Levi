---
skill_id: red_ad_enumeration
name: Active Directory Enumeration Test
description: Test AD enumeration paths to validate LDAP auditing and enumeration detection.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, active-directory, ldap]
version: 1.0.0
team: red
tests_blue: cyber_performing_active_directory_bloodhound_analysis
---
# Active Directory Enumeration Test

## Purpose

AD enumeration is step zero of most intrusions and it's unauthenticated-adjacent: any
domain user can read most of the directory. This test maps what enumeration reveals and
whether bulk LDAP queries trip any monitoring at all.

## When to use

- Early in AD phases, with any domain user context.
- To validate LDAP query monitoring and honeypot-object deployment.
- To scope what an attacker learns before touching a privileged account.

## Prerequisites

- Authorization for the AD environment; standard domain user context.
- Enumeration tooling authorized (built-in + lab-standard).

## Procedure

1. Enumerate with built-in tools first: net user /domain, dsquery-style LDAP, PowerShell AD
   module — record what each reveals.
2. Run bulk enumeration (all users, groups, computers, SPNs, trusts) and measure: did any
   query volume alert?
3. Map trust relationships, privileged groups, and stale objects (the attack-planning
   view).
4. Check for honeypot accounts/objects: do they exist, and did touching them alert?
5. Deliver the AD-exposure map with LDAP-monitoring and honeypot recommendations.

## Expected outputs

- AD enumeration results (users, groups, trusts, SPNs).
- Query-volume detection assessment.
- Honeypot coverage findings.

## Pitfalls

- Bulk queries during business hours without coordination — they can load DCs.
- Touching honeypots without telling the blue team the test includes them — coordinate.
- Exporting the full directory off-network — analyze in place.

## References

- MITRE ATT&CK: Account Discovery, Group Discovery (T1087, T1069).

## Blue-team control under test

This playbook validates their AD is readable by design — the test measures whether
anyone watches the reading, and whether deception exists. Paired blue-team counterpart:
`cyber_performing_active_directory_bloodhound_analysis`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
