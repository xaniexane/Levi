---
skill_id: red_ransomware_negotiation_drill
name: Ransomware Negotiation Drill
description: Drill ransomware negotiation and decision-making as a tabletop exercise.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, impact, ransomware, exercise]
version: 1.0.0
team: red
tests_blue: cyber_performing_ransomware_tabletop_exercise
---
# Ransomware Negotiation Drill

## Purpose

The ransom decision gets made under pressure — this drill makes it beforehand. A
tabletop exercise walking leadership through the ransom demand, the legal constraints,
and the recovery math, so the real incident isn't the first discussion.

## When to use

- As a leadership tabletop, independent of technical phases.
- After the ransomware-impact lab test, using its recovery numbers.
- To validate cyber-insurance and legal notification workflows.

## Prerequisites

- Leadership participation; legal counsel involvement.
- Recovery metrics from the lab test as input.

## Procedure

1. Present the scenario: canary ransomware event with the lab's real recovery numbers.
2. Walk the decision tree: pay vs. rebuild, legal constraints, notification obligations.
3. Test the communications plan: who speaks, what gets said, when.
4. Validate the insurance notification workflow and coverage understanding.
5. Deliver the drill report with decision-playbook recommendations.

## Expected outputs

- Decision-tree walkthrough with leadership positions.
- Communications-plan gaps.
- Insurance/legal workflow findings.

## Pitfalls

- Making the actual pay/don't-pay decision in the drill — the drill builds the playbook,
  leadership decides in the moment.
- Skipping legal — ransom payments have sanctions implications.

## References

- CISA ransomware guidance; FBI IC3 guidance.

## Blue-team control under test

This playbook validates their leadership gets the ransom decision before the crisis —
the playbook is the deliverable. Paired blue-team counterpart:
`cyber_performing_ransomware_tabletop_exercise`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
