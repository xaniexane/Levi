---
skill_id: red_container_escape_test
name: Container Escape Test
description: Test container escape paths in a lab to validate container runtime hardening and monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, execution, containers, lab]
version: 1.0.0
team: red
tests_blue: cyber_core_container_escape
---
# Container Escape Test

## Purpose

Containers promise isolation; misconfigurations break it. This lab-only test exercises
classic escape paths — privileged containers, hostPath mounts, Docker socket exposure,
kernel exploits — to validate runtime hardening and container telemetry before
production workloads are at risk.

## When to use

- When the org runs containerized workloads and the threat model includes container
  breakout.
- To validate PodSecurity policies and runtime security monitoring.
- Lab-only — never against production clusters.

## Prerequisites

- Isolated lab cluster mirroring the production configuration; no production contact.
- Authorization for escape testing in the lab with defined escape goals (host file read,
  not host damage).

## Procedure

1. Deploy the standard misconfiguration matrix in the lab: privileged pod, hostPath mount,
   docker.sock mount, hostNetwork, excessive capabilities.
2. Attempt each escape path with proof-only goals: read a host canary file, never modify
   the host.
3. Test runtime security monitoring: does Falco/Tetragon-style telemetry fire on each
   escape attempt?
4. Validate PodSecurity admission: which misconfigurations were blocked at deploy time vs.
   which ran?
5. Test image-scanning gates: do known-vulnerable images get blocked before the escape test
   even starts?
6. Deliver the escape-path matrix with admission-policy and monitoring recommendations.

## Expected outputs

- Per-misconfiguration escape feasibility and detection matrix.
- Admission-controller effectiveness assessment.
- Runtime-monitoring rule recommendations.

## Pitfalls

- Testing against production or staging clusters — lab only, always.
- Escape goals that damage the host — proof is a canary read, nothing more.
- Forgetting the CI/CD supply chain: image provenance matters as much as runtime config.

## References

- MITRE ATT&CK: Escape to Host (T1611).
- Kubernetes PodSecurity standards documentation.

## Blue-team control under test

This playbook validates their admission policies and container runtime monitoring get a
full matrix — escapes that ran silently are runtime-security gaps. Paired blue-team
counterpart: `cyber_core_container_escape`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
