---
skill_id: grey_identity_synthetic_users
name: Synthetic Identity Provisioning
description: Provision synthetic users, service accounts, and personas for exercise realism.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, identity, personas]
version: 1.0.0
team: grey
---
# Synthetic Identity Provisioning

## Purpose

Exercises need people: users with mailboxes and files, admins with habits, service
accounts with SPNs. This runbook provisions synthetic identities — realistic, clearly
labeled, and scoped to the range — so red-team targeting and blue-team UEBA have
something real to work with.

## When to use

- For any exercise needing user realism.
- For phishing and social-engineering scenarios (synthetic targets).
- For UEBA/anomaly-detection exercises needing behavioral baselines.

## Prerequisites

- Persona roster for the scenario (roles, privileges, behaviors).
- Identity infrastructure (AD/lab IdP) ready.

## Procedure

1. Create the persona accounts per the roster: naming convention marking them synthetic.
2. Build behavioral baselines: logon patterns, mailbox content, file activity — scripted
   where possible.
3. Create service accounts with the scenario's SPNs and documented password hygiene.
4. Provision mailboxes, home drives, and cloud identities per the scenario.
5. Document the persona catalog: who exists, what they do, what's deliberate.
6. Hand over with the identity inventory; schedule deprovisioning with range teardown.

## Expected outputs

- Persona catalog with behaviors.
- Identity inventory.
- Deprovisioning schedule.

## Pitfalls

- Synthetic users indistinguishable from real ones — naming and documentation must mark
  them.
- Realistic mailboxes with real sensitive content — canary content only.
- Service accounts with passwords that leak into real vaults — range-scoped secrets
  only.

## References

- Identity-management literature; UEBA baseline guidance.

## Exercise role

Synthetic people make the exercise real — labeled clearly enough that nobody confuses
the stage with the world.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
