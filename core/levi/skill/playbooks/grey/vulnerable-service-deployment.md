---
skill_id: grey_vulnerable_service_deployment
name: Vulnerable Service Deployment
description: Deploy intentionally vulnerable services per scenario with safety containment.
risk: low
permissions: []
requires_confirmation: false
tags: [grey-team, provisioning, vulnerable, services]
version: 1.0.0
team: grey
---
# Vulnerable Service Deployment

## Purpose

Some scenarios need vulnerable targets: unpatched services, misconfigured apps, weak
credentials — deliberately deployed, documented, and contained. This runbook deploys
them safely.

## When to use

- For exploitation-focused exercises.
- When the scenario's attack path starts at a vulnerable service.
- For vulnerability-management validation exercises.

## Prerequisites

- Scenario's vulnerability list with intended attack paths.
- Containment verification (no production routes).
- Blue-team awareness of which vulnerabilities are deliberate.

## Procedure

1. Deploy the vulnerable services per the scenario list — version-pinned, documented.
2. Apply the intended misconfigurations; ticket each as deliberate.
3. Verify containment: vulnerable services unreachable outside the range.
4. Instrument: full logging on vulnerable hosts (the exploitation must be visible).
5. Brief the blue team: which vulnerabilities are deliberate and which paths are in scope.
6. Hand over with the vulnerability register.

## Expected outputs

- Vulnerable-service inventory with versions.
- Deliberate-misconfiguration register.
- Containment and logging verification.

## Pitfalls

- Vulnerable services reachable from production or the internet — containment first.
- Undocumented vulnerabilities — the blue team wastes the exercise chasing stage props.
- Vulnerable services with real data — canary data only.

## References

- Vulnerability-management literature; CVE documentation.

## Exercise role

Vulnerable-by-design targets are stage props — documented, contained, and never mistaken
for real findings.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
