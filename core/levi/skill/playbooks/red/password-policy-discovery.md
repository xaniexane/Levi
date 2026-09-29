---
skill_id: red_password_policy_discovery
name: Password Policy Discovery Test
description: Discover effective password policy to validate policy enforcement and fine-grained policies.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, password-policy]
version: 1.0.0
team: red
tests_blue: cyber_auditing_azure_active_directory_configuration
---
# Password Policy Discovery Test

## Purpose

Attackers read the password policy to tune their attacks; defenders should know what's
actually enforced. This test discovers the effective policy — domain default, fine-
grained, and cloud — and validates it matches the documented standard.

## When to use

- During discovery phases.
- To validate fine-grained password policies apply where intended.
- As input to the hash-cracking lab's policy verdict.

## Prerequisites

- Authorization for the domain; standard user context.

## Procedure

1. Read the domain password policy (net accounts /domain, AD module) and all fine-grained
   policies.
2. Check cloud policy: Azure AD / Entra password protection status and custom banned lists.
3. Verify enforcement matches documentation: test canary accounts against the stated
   complexity (authorized).
4. Flag discrepancies: documented 14 characters, enforced 8.
5. Deliver the policy-vs-enforcement assessment.

## Expected outputs

- Effective policy per scope (domain, FGPP, cloud).
- Documentation-vs-enforcement deltas.
- Canary enforcement-test results.

## Pitfalls

- Testing enforcement with real user accounts — canary accounts only.
- Forgetting cloud policy while auditing on-prem — cover both.

## References

- MITRE ATT&CK: Password Policy Discovery (T1201).
- NIST SP 800-63B (password guidance).

## Blue-team control under test

This playbook validates their documented policy vs. enforced reality is compared —
deltas are compliance findings with canary proof. Paired blue-team counterpart:
`cyber_auditing_azure_active_directory_configuration`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
