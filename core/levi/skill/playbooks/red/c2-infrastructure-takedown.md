---
skill_id: red_c2_infrastructure_takedown
name: C2 Infrastructure Takedown Exercise
description: Exercise C2 infrastructure takedown procedures as a blue-team validation drill.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, command-and-control, takedown, exercise]
version: 1.0.0
team: red
tests_blue: cyber_building_incident_response_playbook
---
# C2 Infrastructure Takedown Exercise

## Purpose

This is the rare red playbook that's really a blue drill: given canary C2
infrastructure, the blue team practices the takedown — domain sinkholing coordination,
firewall blocks, endpoint isolation — and the red side measures their speed and
completeness.

## When to use

- As a joint exercise after C2 testing phases.
- To validate incident-response playbooks for C2 infrastructure.
- To measure takedown coordination across teams.

## Prerequisites

- Canary C2 infrastructure designated as the takedown target.
- IR playbook and stakeholder coordination.

## Procedure

1. Stand up the canary C2 infrastructure and generate realistic beacon traffic.
2. Hand the blue team the detection (simulated initial alert) and start the clock.
3. Observe the takedown: containment, blocking, sinkholing coordination, endpoint
   isolation.
4. Measure: time to containment, completeness (did all infrastructure get blocked?),
   communication quality.
5. Red-team debrief: which takedown steps were missed or slow?
6. Deliver the takedown exercise report with playbook improvements.

## Expected outputs

- Takedown timeline with measurements.
- Completeness assessment (infrastructure blocked?).
- IR playbook improvement recommendations.

## Pitfalls

- Real infrastructure as the target — canary only.
- Grading individuals instead of the playbook — keep it blameless.

## References

- Incident-response exercise literature; C2 takedown case studies (public).

## Blue-team control under test

This playbook validates their IR playbook gets a live-fire drill — takedown speed and
completeness are the measured outcomes. Paired blue-team counterpart:
`cyber_building_incident_response_playbook`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
