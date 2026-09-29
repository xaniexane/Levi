---
skill_id: red_user_hunting_test
name: User Hunting and Session Discovery Test
description: Test user/session discovery to validate session monitoring and privileged-user hygiene.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, users, sessions]
version: 1.0.0
team: red
tests_blue: cyber_implementing_privileged_session_monitoring
---
# User Hunting and Session Discovery Test

## Purpose

Knowing who's logged in where tells an attacker where the privileged sessions are. This
test performs user and session discovery — logged-on users, RDP sessions, service
sessions — and validates whether session enumeration is monitored and privileged
sessions are hygienic.

## When to use

- During discovery phases on Windows networks.
- To validate privileged-session hygiene (no DA sessions on workstations).
- To test detection of session-enumeration tooling.

## Prerequisites

- Authorization for the target hosts; standard user context.

## Procedure

1. Enumerate logged-on users and sessions on target hosts (qwinsta, net session,
   PSLoggedOn-style).
2. Map privileged sessions: are Domain Admins logged into workstations or member servers?
3. Check for disconnected RDP sessions holding privileged tokens.
4. Record whether the enumeration tripped any monitoring.
5. Deliver the session-hygiene findings with privileged-access-workstation recommendations.

## Expected outputs

- Session map with privilege analysis.
- Privileged-session hygiene findings.
- Enumeration-detection assessment.

## Pitfalls

- Session enumeration on sensitive hosts (executive, HR) without specific approval.
- Hijacking disconnected sessions — discovery only, no session takeover without
  approval.

## References

- MITRE ATT&CK: System Owner/User Discovery (T1033).
- Microsoft: privileged access guidance.

## Blue-team control under test

This playbook validates their privileged-session hygiene is under test — Domain Admin
sessions on workstations are the finding that justifies PAWs. Paired blue-team
counterpart: `cyber_implementing_privileged_session_monitoring`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
