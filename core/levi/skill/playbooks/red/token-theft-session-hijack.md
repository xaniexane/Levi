---
skill_id: red_token_theft_session_hijack
name: Token Theft and Session Hijacking Test
description: Test access-token and session-cookie theft to validate session-security controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, tokens, session]
version: 1.0.0
team: red
tests_blue: cyber_core_session_hijacking
---
# Token Theft and Session Hijacking Test

## Purpose

Modern auth is token-based; stealing the token skips the password and the MFA. This test
validates token theft paths — memory, disk, browser — and the controls that limit token
value: short lifetimes, binding, and conditional access.

## When to use

- During credential-access phases.
- To validate token-lifetime and binding policies.
- To test conditional-access resilience against stolen sessions.

## Prerequisites

- Authorization for token-handling on test accounts; canary tokens and sessions.
- Token material handled per the credential ROE.

## Procedure

1. With user-context access, enumerate token material: browser session cookies, app token
   caches, memory-resident tokens (canary).
2. Attempt replay of canary tokens from a different host/network — record whether
   conditional access stopped it.
3. Test token-lifetime: how long does a stolen canary token remain valid?
4. Check for token binding / DPoP-style controls in the environment.
5. Destroy all canary token material; verify no test tokens remain valid.
6. Deliver the session-security assessment with lifetime and binding recommendations.

## Expected outputs

- Token-replay results per control (CA, lifetime, binding).
- Token-lifetime measurements.
- Session-security recommendations.

## Pitfalls

- Replaying real user tokens without approval — canary tokens only.
- Token material lingering after the test — verify invalidation.
- Forgetting refresh tokens while focusing on access tokens — test both.

## References

- MITRE ATT&CK: Steal Application Access Token (T1528).

## Blue-team control under test

This playbook validates their session-security architecture is under test — replayable
long-lived tokens are a lifetime-and-binding finding. Paired blue-team counterpart:
`cyber_core_session_hijacking`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
