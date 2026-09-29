---
skill_id: grey_response_scoring
name: Response Scoring
description: Score blue-team response: containment, eradication, and recovery actions.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, scoring, response, blue-team]
version: 1.0.0
team: grey
---
# Response Scoring

## Purpose

Detection without response is a weather report. This scoring evaluates what the blue
team did with their detections: triage quality, containment speed and correctness,
eradication completeness, and recovery — each against evidence.

## When to use

- After exercise execution, during evaluation.
- For IR-validation exercises especially.

## Prerequisites

- Scoring model with response elements.
- Evidence: tickets, comms, action logs, containment records.

## Procedure

1. Score triage: was the alert correctly prioritized and assigned? (Evidence: ticket/SOC
   records.)
2. Score containment: speed (detection to isolation) and correctness (right scope, no
   collateral).
3. Score eradication: was the red presence actually removed? (Verify with the red team.)
4. Score recovery: systems restored, verified clean, returned to service per the runbook.
5. Score communications: notifications made, stakeholders informed, per the comms plan.
6. Publish response scores with evidence and the red-team's verification of eradication.

## Expected outputs

- Response scorecard per phase.
- Containment/eradiation verification.
- Communications assessment.

## Pitfalls

- Eradication scored without red-team verification — confirm the removal.
- Speed scored without correctness — fast wrong containment is a penalty, not a win.

## References

- Incident-response literature; NIST SP 800-61.

## Exercise role

Response scoring measures what happened after the alert — the part of the exercise that
actually protects the organization.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
