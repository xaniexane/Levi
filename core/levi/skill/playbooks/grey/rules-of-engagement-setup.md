---
skill_id: grey_rules_of_engagement_setup
name: Rules of Engagement Setup
description: Draft, approve, and publish exercise rules of engagement.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, setup, roe, governance]
version: 1.0.0
team: grey
---
# Rules of Engagement Setup

## Purpose

The ROE is the exercise's contract: what's in scope, what's forbidden, who authorizes
what, and what happens when something goes wrong. This setup produces a signed ROE
before any red action — no ROE, no exercise.

## When to use

- During exercise planning, before any execution.
- When scope changes mid-exercise (ROE amendment).

## Prerequisites

- Exercise objectives and scope proposal.
- Stakeholder list for approvals.
- Legal/HR review where required.

## Procedure

1. Draft the ROE: scope (hosts, accounts, networks), authorized techniques, forbidden
   actions, time windows.
2. Define the authorization chain: who approves what, how fast, and the emergency-stop
   authority.
3. Define handling rules: credentials, sensitive data, destructive techniques, production-
   adjacent systems.
4. Route for approvals: exercise director, system owners, legal/HR as needed — collect
   signatures.
5. Publish the signed ROE to the artifact repository; brief all participants.
6. Establish the amendment process for mid-exercise scope changes.

## Expected outputs

- Signed rules of engagement.
- Authorization chain with contacts.
- Amendment process.

## Pitfalls

- Verbal ROE — if it isn't signed, it isn't the ROE.
- Forbidden actions left vague — enumerate them.
- No emergency-stop authority defined — define it before you need it.

## References

- Penetration-testing ROE literature; PTES.

## Exercise role

The ROE is what makes red-team work a professional exercise instead of an incident —
signed before anything runs.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
