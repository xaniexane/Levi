---
skill_id: grey_real_time_adjudication
name: Real-Time Adjudication
description: Adjudicate exercise events in real time: fairness calls and boundary rulings.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, referees, adjudication, exercise]
version: 1.0.0
team: grey
---
# Real-Time Adjudication

## Purpose

Exercises need calls in the moment: is this technique in bounds, did that detection
happen before the deadline, is the red team still in scope? This is the real-time
adjudication function — fast, fair, and documented.

## When to use

- During exercise execution.
- Whenever a boundary or fairness question arises.

## Prerequisites

- Referee charter.
- Referee access to team nets and the scenario.

## Procedure

1. Receive the adjudication request: who, what, when, what's at stake.
2. Rule against the ROE, the scenario, and the charter — quickly; the exercise doesn't
   pause for deliberation.
3. Communicate the ruling to affected teams immediately and log it.
4. For safety issues, rule first and document after — safety outranks procedure.
5. Track ruling patterns: repeated disputes about the same rule signal a charter gap.
6. Hand the ruling log to the after-action.

## Expected outputs

- Real-time ruling log.
- Charter-gap notes.
- Safety-stop record (if any).

## Pitfalls

- Slow adjudication stalling the exercise — decide fast, document after.
- Safety questions treated as normal disputes — safety rules first.
- Inconsistent rulings across referees — one charter, calibrated referees.

## References

- Officiating literature.

## Exercise role

Real-time adjudication keeps the exercise fair at speed — fast rulings, logged always,
safety first.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
