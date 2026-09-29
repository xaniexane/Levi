---
skill_id: grey_internet_simulator_provisioning
name: Internet Simulator Provisioning
description: Provision a simulated internet for closed ranges with fake external services.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, simulation, internet]
version: 1.0.0
team: grey
---
# Internet Simulator Provisioning

## Purpose

Closed ranges can't reach the real internet — so the grey team simulates it: fake DNS,
fake web services, simulated C2 infrastructure, fake update servers. This runbook builds
the simulator so exfiltration and C2 exercises have somewhere to go.

## When to use

- For closed/air-gapped ranges.
- For C2 and exfiltration exercises needing external destinations.
- To keep exercise traffic off the real internet.

## Prerequisites

- Closed-range network design with the simulator segment.
- Service list: what the scenario needs (DNS, HTTP, mail, cloud APIs).

## Procedure

1. Deploy the simulator host(s): DNS resolver with exercise zones, web servers with canary
   content.
2. Simulate the scenario's external services: C2 endpoints, exfil destinations, phishing
   infrastructure.
3. Configure range DNS to resolve through the simulator; sinkhole everything else with
   logging.
4. Verify containment: simulator traffic never leaves the range.
5. Instrument the simulator: full request logging for the blue team's analysis.
6. Hand over with the simulator service catalog.

## Expected outputs

- Simulator service catalog.
- Containment-verification evidence.
- Simulator logging verification.

## Pitfalls

- Simulator with a real upstream resolver — that's a leak, not a simulator.
- Unlogged simulator services — the blue team needs the simulator's logs too.
- Phishing infrastructure in the simulator confusing real users — label everything.

## References

- Range-operations literature; DNS RPZ documentation.

## Exercise role

The simulated internet is where exercise attacks land — contained, logged, and
unmistakably fake.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
