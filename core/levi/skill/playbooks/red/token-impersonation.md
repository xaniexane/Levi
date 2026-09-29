---
skill_id: red_token_impersonation
name: Token Impersonation Test
description: Test token impersonation and potato-family escalation paths in a lab to validate token monitoring.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, privilege-escalation, tokens, windows, lab]
version: 1.0.0
team: red
tests_blue: cyber_core_token_impersonation
---
# Token Impersonation Test

## Purpose

Windows access tokens can be stolen and impersonated; the 'potato' family chains this
with DCOM/NtLM quirks into SYSTEM. This lab test validates token-theft monitoring and
whether the specific potato prerequisites (SeImpersonatePrivilege) are even present in
the environment.

## When to use

- Lab-first, during Windows privilege-escalation phases.
- To validate that service accounts hold only the privileges they need.
- To test EDR detection of token-manipulation APIs.

## Prerequisites

- Lab authorization; production only with explicit approval and a maintenance window.
- Inert proof goals (whoami / privileges output), never destructive.

## Procedure

1. Enumerate privileges of the test context (`whoami /priv`); confirm
   SeImpersonatePrivilege or SeAssignPrimaryTokenPrivilege is present.
2. In the lab, execute the potato-chain variant matching the OS version; capture the SYSTEM
   token.
3. Verify escalation with inert proof (privilege listing as SYSTEM).
4. Record EDR telemetry: which API calls (DuplicateToken, ImpersonateLoggedOnUser) were
   flagged.
5. Test the mitigation: remove SeImpersonatePrivilege from the service account and re-run
   to prove the chain breaks.
6. Deliver the privilege-hygiene findings: which accounts hold dangerous privileges
   unnecessarily.

## Expected outputs

- Token-impersonation feasibility per OS/service-account combination.
- EDR API-monitoring assessment.
- Privilege-reduction verification (re-test after hardening).

## Pitfalls

- Running potato exploits against production without a window — they can crash hosts.
- Assuming all potato variants work everywhere — match the variant to the OS build in
  the lab first.
- Forgetting the mitigation test — proving the fix works is half the finding.

## References

- MITRE ATT&CK: Access Token Manipulation (T1134).
- Public potato-family research (Google Project Zero et al.).

## Blue-team control under test

This playbook validates their service-account privilege hygiene is the real finding —
SeImpersonatePrivilege on web-facing service accounts is the gap, the exploit is just
the proof. Paired blue-team counterpart:
`cyber_core_token_impersonation`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
