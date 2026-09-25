---
skill_id: cyber_performing_kubernetes_penetration_testing
name: Kubernetes Penetration Testing
description: Scope and execute an authorized Kubernetes security assessment.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, pentest, assessment]
version: 1.0.0
---
# Kubernetes Penetration Testing

## Purpose

Kubernetes adds a dense layer of attack surface — RBAC, pod security,
network policy, secrets handling, supply chain — on top of familiar
infrastructure. This playbook scopes and executes an authorized
Kubernetes penetration test from the defender's perspective, with an
emphasis on the flaws that actually lead to cluster compromise.

## When to use

- Annual or compliance-driven assessment of production clusters.
- After major platform changes: new ingress, service mesh, or
  multi-tenancy.
- Validating remediation of prior Kubernetes findings.
- Pre-launch review of a new platform offering.

## Prerequisites

- Written authorization defining clusters, namespaces, and test
  identities (unauthenticated, low-privilege service account,
  developer role), plus the testing window.
- For managed services, confirm the provider's testing policy; some
  prohibit control-plane testing.
- Tooling: kubectl with test kubeconfigs, kube-hunter or similar for
  enumeration, and an intercepting proxy for API testing.

## Procedure

1. Finalize scope and ROE: which clusters and namespaces, whether
   privilege escalation to cluster-admin is in scope, and what
   constitutes a stopping point (production impact, data access).
2. Enumerate from outside: exposed API servers, dashboards, etcd, and
   kubelet ports; anonymous API access checks; and ingress-exposed
   services.
3. Test RBAC from each identity: list what each test account can do
   across namespaces — look for wildcard verbs, cluster-admin
   bindings, and roles that permit secret reads or pod exec.
4. Attempt pod escape and privilege escalation paths: hostPath mounts,
   privileged pods, host networking/PID, overly permissive service
   accounts (especially default ones with token automount).
5. Test network segmentation: from a compromised-pod position, probe
   whether NetworkPolicies actually isolate namespaces and block
   metadata or internal services.
6. Review secrets handling: secrets in environment variables versus
   mounted volumes, etcd encryption, and whether CI/CD pipelines or
   dashboards expose them.
7. Check the supply chain: image provenance (signed? scanned?),
   admission controllers in place, and whether unsigned or
   latest-tagged images can deploy.
8. Document with reproduction: each finding needs the exact kubectl
   commands or manifests, the identity used, and the impact — plus
   concrete remediation (RBAC least privilege, Pod Security
   Standards, NetworkPolicies).

## Expected outputs

- Findings with reproducible evidence per test identity.
- An RBAC over-permission inventory.
- Network segmentation verification results.
- Remediation guidance and a retest plan.

## Pitfalls

- Testing only as cluster-admin: the interesting flaws appear at low
   privilege.
- Disruptive tests in production: pod deletion and resource
   exhaustion belong in staging.
- Ignoring the CI/CD pipeline: cluster access via pipelines is often
   the real privileged path.
- Equating a clean test with ongoing security: pair with continuous
   configuration scanning.

## References

- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- Kubernetes documentation: securing the cluster
- MITRE ATT&CK: Containers matrix
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
