---
skill_id: red_domain_fronting_test
name: Domain Fronting Validation Test
description: Test domain-fronting concepts to validate SNI inspection and CDN controls.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, domain-fronting]
version: 1.0.0
team: red
tests_blue: cyber_hunting_for_domain_fronting_c2_traffic
---
# Domain Fronting Validation Test

## Purpose

Domain fronting hides the true destination behind a trusted front domain. This test
validates — with canary traffic — whether SNI inspection, CDN policies, and proxy
controls would distinguish fronted traffic from legitimate CDN use.

## When to use

- During C2 phases, where CDN usage is heavy.
- To validate SNI-visibility and fronting-detection controls.
- As a TLS-inspection complement.

## Prerequisites

- Authorization for the test; canary front/back infrastructure.
- Understanding of current CDN fronting mitigations (many CDNs now block it — the test
  verifies).

## Procedure

1. Attempt canary domain-fronted connections through the CDNs in use.
2. Record whether the CDN blocked the fronting (many now do) and whether the proxy
   distinguished the traffic.
3. Test the SNI-visibility: what does the monitoring see — front domain, back domain, or
   neither?
4. Document which CDNs permit fronting-like patterns and which block.
5. Tear down canary infrastructure.
6. Deliver the fronting assessment with SNI-inspection recommendations.

## Expected outputs

- Per-CDN fronting feasibility results.
- SNI-visibility assessment.
- Monitoring recommendations.

## Pitfalls

- Assuming fronting still works everywhere — verify per CDN, document blocks as the
  control working.
- Real data over fronted channels — canary traffic only.

## References

- MITRE ATT&CK: Proxy — domain fronting concepts; CDN provider documentation.

## Blue-team control under test

This playbook validates their SNI inspection and CDN controls are under test — frontable
paths are the finding, blocked paths are the control working. Paired blue-team
counterpart: `cyber_hunting_for_domain_fronting_c2_traffic`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
