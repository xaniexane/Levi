---
skill_id: red_fallback_channel_test
name: C2 Fallback Channel Test
description: Test C2 fallback and dead-drop channels to validate layered egress monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, command-and-control, fallback, egress]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_cobaltstrike_malleable_c2_profiles
---
# C2 Fallback Channel Test

## Purpose

C2 frameworks fall back through channels when the primary is blocked — DNS to HTTPS to
cloud APIs to dead drops. This test exercises the fallback chain with canary traffic and
validates that blocking one channel doesn't just move the problem silently.

## When to use

- During C2 phases, after primary-channel tests.
- To validate defense-in-depth across egress channels.
- To test dead-drop resolver and social-media C2 concepts.

## Prerequisites

- Authorization for multi-channel C2 testing; canary infrastructure per channel.

## Procedure

1. Block the primary canary channel (simulating the defense working) and observe fallback
   behavior.
2. Exercise each fallback: alternate protocol, cloud-API dead drop, legitimate-service
   signaling.
3. Record per-channel detection as the fallback chain executes.
4. Test dead-drop concepts: canary messages via cloud storage/comments (authorized test
   accounts).
5. Tear down all canary channels.
6. Deliver the fallback-chain assessment: which fallbacks were silent?

## Expected outputs

- Fallback-chain execution log with per-channel detection.
- Silent-fallback findings.
- Layered-egress recommendations.

## Pitfalls

- Dead drops on real public platforms without authorization — test accounts only.
- Leaving fallback infrastructure active — tear down every channel.

## References

- MITRE ATT&CK: Fallback Channels (T1008).

## Blue-team control under test

This playbook validates their egress defense-in-depth is under test — every silent
fallback is a channel the blocking strategy doesn't cover. Paired blue-team counterpart:
`cyber_analyzing_cobaltstrike_malleable_c2_profiles`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
