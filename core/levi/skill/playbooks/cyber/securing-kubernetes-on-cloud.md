---
skill_id: cyber_securing_kubernetes_on_cloud
name: Securing Kubernetes on Cloud
description: Harden managed Kubernetes: private control plane, RBAC, network policies, pod security, and image governance.
risk: info
permissions: []
requires_confirmation: false
tags: [kubernetes, cloud, hardening]
version: 1.0.0
---
## Purpose
Managed Kubernetes (EKS, GKE, AKS) secures the control plane for you but leaves cluster configuration to the operator. This playbook provides a hardening baseline: private endpoints, strong RBAC, network policies, pod security standards, secrets management, and image governance.

## When to use
- New cluster provisioning or landing-zone baseline.
- Security review of existing production clusters.
- Compliance evidence for containerized workloads.
- After a cluster security incident or penetration test.

## Prerequisites
- Cloud admin access and the cluster provisioning method (IaC preferred).
- Identity provider integration for RBAC (Entra ID, IAM, Google identities).
- Network design: VPC/VNet layout and private connectivity options.
- Image registry with scanning and signing capability.

## Procedure
1. Deploy private clusters: private control-plane endpoint, private nodes, no public node IPs.
2. Integrate cluster RBAC with the corporate identity provider; avoid static kubeconfig admin credentials.
3. Apply least-privilege RBAC: namespace-scoped roles, no cluster-admin for humans or CI by default.
4. Enforce Pod Security Standards (restricted) via admission; grant exceptions per namespace with expiry.
5. Implement default-deny network policies and explicit allow rules per application tier.
6. Manage secrets via external secrets operator backed by the cloud KMS/secrets manager; enable envelope encryption for etcd.
7. Require scanned, signed images from approved registries; block `:latest` and public pulls in production.
8. Enable audit logging to the SIEM; alert on privileged pod creation, RBAC changes, and secrets access.
9. Rotate cluster credentials and service account tokens on a schedule.
10. Disable automounting of the default service account token in pods that do not need API access.
11. Audit cloud IAM bindings that grant cluster access; they bypass Kubernetes RBAC reviews.

## Expected outputs
- Cluster hardening baseline with configuration evidence per control.
- RBAC and network-policy inventory.
- Audit logging pipeline and alert rules.
- Credential rotation schedule and compliance log.
- Service-account automount audit results.
- Cloud-IAM-to-cluster access mapping.

## Pitfalls
- Managed control-plane security does not cover your workloads; the shared-responsibility line is often misunderstood.
- Default-deny network policies break applications on first deploy; roll out with monitoring mode where supported.
- Cloud IAM-to-RBAC mappings are a privilege path; review them like any other trust policy.
- Node auto-upgrades can surprise; pin and test Kubernetes versions in non-production first.
- Default service account tokens mounted in every pod are a lateral-movement enabler; opt out.
- Cluster autoscaler and node pools need their own IAM scoping; review them.
- Stale kubeconfig files on engineer laptops are credential sprawl; expire them.
- etcd backups contain all secrets; encrypt and restrict them like production data.

## References
- NIST SP 800-190, Application Container Security Guide.
- CIS Kubernetes Benchmarks and cloud-provider CIS benchmarks.
- Cloud provider Kubernetes security best-practices documentation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
