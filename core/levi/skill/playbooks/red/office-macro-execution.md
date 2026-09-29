---
skill_id: red_office_macro_execution
name: Office Macro Execution Test
description: Test Office macro execution paths and trust settings to validate macro-blocking policies.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, office, macros]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_macro_malware_in_office_documents
---
# Office Macro Execution Test

## Purpose

Macros remain a top initial-execution vector. This test walks the macro execution paths
— auto-open macros, XLM 4.0, VBA stomping concepts — against the organization's macro-
blocking policy, using inert documents. The goal is a policy verdict, not a payload.

## When to use

- When the org's macro policy is 'block all' or 'signed only' and needs validation.
- After the phishing attachment test shows documents reach inboxes.
- To test EDR behavior on macro-spawned processes.

## Prerequisites

- Authorization for macro-execution testing; documents inert and client-approved.
- Knowledge of the deployed Office versions and macro GPOs.

## Procedure

1. Build inert macro documents: VBA auto-open writing a canary, XLM 4.0 sheet executing a
   canary formula.
2. Test each against the macro policy matrix: internet-zone documents, trusted locations,
   signed vs. unsigned.
3. Record the user experience: blocked silently, warned, or executed — per Office version
   in the baseline.
4. For executed macros, record the child-process telemetry (EDR/Sysmon) of the canary
   action.
5. Test policy-bypass-adjacent paths only as authorized (trusted-location abuse); report,
   don't exploit, trust boundaries.
6. Deliver the macro-policy verdict with GPO recommendations.

## Expected outputs

- Macro execution matrix per document type × policy zone.
- Child-process telemetry for executed macros.
- Macro GPO hardening recommendations.

## Pitfalls

- Malicious macro payloads — inert canaries only, always.
- Testing only one Office version when the fleet is mixed.
- Confusing 'macro blocked' with 'document safe' — the attachment test covers delivery;
  this covers execution.

## References

- MITRE ATT&CK: Office Application Startup — Office Test (T1137).
- Microsoft: macro security guidance.

## Blue-team control under test

This playbook validates their Office macro GPOs and EDR child-process monitoring get a
full matrix — any executed macro is a policy failure to remediate. Paired blue-team
counterpart: `cyber_analyzing_macro_malware_in_office_documents`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
