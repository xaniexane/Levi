---
skill_id: red_sabotage_scenario_test
name: Sabotage Scenario Test
description: Exercise insider-sabotage scenarios as a tabletop-plus-validation drill.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, impact, sabotage, insider]
version: 1.0.0
team: red
tests_blue: cyber_core_insider_data_theft
---
# Sabotage Scenario Test

## Purpose

Sabotage by a trusted insider is the impact scenario technical controls handle worst.
This exercise — tabletop plus canary validation — tests what a malicious insider could
destroy and which controls would slow or catch them.

## When to use

- As a joint exercise with HR/legal/security leadership.
- To validate insider-threat controls and separation of duties.
- To test backup and recovery against the malicious-admin case.

## Prerequisites

- Exercise authorization with leadership; canary systems/data.
- Legal/HR coordination — insider scenarios are sensitive.

## Procedure

1. Tabletop: walk the malicious-insider scenarios (data destruction, logic bombs,
   credential abuse).
2. Validate technically with canary actions: what CAN the test insider account actually
   destroy?
3. Check separation of duties: can one account both destroy and delete the backups?
4. Test detection: would the canary sabotage alert anyone?
5. Deliver the sabotage-readiness report with control recommendations.

## Expected outputs

- Scenario walkthrough with feasibility ratings.
- Canary-validation results.
- Separation-of-duties findings.

## Pitfalls

- Real destructive actions — canary only, always.
- Framing findings as accusations — this tests controls, not people.

## References

- Insider-threat literature (CERT, CISA).

## Blue-team control under test

This playbook validates their insider-threat posture is exercised — single points of
destructive trust are the findings. Paired blue-team counterpart:
`cyber_core_insider_data_theft`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
