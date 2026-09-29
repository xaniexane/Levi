---
skill_id: red_container_discovery
name: Container and Orchestration Discovery Test
description: Test container-escape-surface discovery to validate Kubernetes RBAC and audit logging.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, discovery, containers, kubernetes]
version: 1.0.0
team: red
tests_blue: cyber_auditing_kubernetes_cluster_rbac
---
# Container and Orchestration Discovery Test

## Purpose

A compromised pod is a foothold with an API server next door. This test enumerates the
container's view — service account tokens, mounted secrets, the API server — to validate
Kubernetes RBAC, pod security standards, and audit logging.

## When to use

- During container phases, from a test pod.
- To validate pod security standards and service-account hygiene.
- To test Kubernetes audit-log coverage of discovery queries.

## Prerequisites

- Authorization for the test namespace/cluster; test pod with representative service
  account.
- Read-only discovery; escape attempts need separate approval.

## Procedure

1. From the test pod, enumerate: service-account token, mounted secrets, environment
   variables, node metadata access.
2. Query the API server with the pod's credentials: what can this service account list and
   get?
3. Check for host mounts, privileged flags, and host-network in the pod spec.
4. Verify Kubernetes audit logs captured the discovery queries.
5. Deliver the pod-security assessment with RBAC and policy recommendations.

## Expected outputs

- Pod-visible secret and API enumeration results.
- Service-account permission analysis.
- Kubernetes audit-log assessment.

## Pitfalls

- Escaping the container without explicit approval — discovery only unless authorized.
- Reading real mounted secrets beyond canary verification — report existence, handle
  values per ROE.
- Testing in production namespaces without isolation — use the test namespace.

## References

- MITRE ATT&CK: Container Administration Command; Kubernetes RBAC documentation.

## Blue-team control under test

This playbook validates their Kubernetes RBAC and pod security standards are under test
— over-permissive service accounts are the container finding. Paired blue-team
counterpart: `cyber_auditing_kubernetes_cluster_rbac`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
