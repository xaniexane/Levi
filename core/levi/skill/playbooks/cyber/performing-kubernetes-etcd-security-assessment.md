---
skill_id: cyber_performing_kubernetes_etcd_security_assessment
name: Kubernetes etcd Security Assessment
description: Assess and harden the etcd datastore backing Kubernetes.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, etcd, hardening]
version: 1.0.0
---
# Kubernetes etcd Security Assessment

## Purpose

etcd holds every Kubernetes secret, ConfigMap, and cluster state — it is
the crown jewel of the control plane. This playbook assesses etcd's
security posture: transport encryption, authentication, data-at-rest
protection, and backup hygiene, and hardens each layer.

## When to use

- Security review of a Kubernetes control plane.
- After etcd-related findings in a kube-bench or penetration test.
- Validating backup and disaster-recovery handling of etcd data.
- Pre-production sign-off for a new cluster.

## Prerequisites

- Administrative access to the etcd configuration (static pod
  manifests, kubeadm config, or managed-service settings).
- Knowledge of the etcd topology: members, endpoints, and which
  components communicate with it.
- A maintenance window for changes that restart etcd members.

## Procedure

1. Verify TLS everywhere: etcd peer and client communication must use
   TLS with client-certificate authentication — no plaintext
   listeners, no unauthenticated endpoints.
2. Check certificate hygiene: certificate expiry, rotation process,
   and that etcd certs are issued by a dedicated CA, not shared with
   unrelated services.
3. Confirm data-at-rest encryption: the API server's
   `--encryption-provider-config` must encrypt secrets in etcd (AES-
   CBC at minimum, AES-GCM or secretbox preferred); verify by
   checking stored secret values are not plaintext.
4. Restrict network access: etcd ports (2379/2380) reachable only from
   control-plane nodes; no workload, node, or external access.
5. Audit etcd access: enable audit logging on the API server for
   secret access, and review who can read secrets at the etcd level
   versus through RBAC.
6. Secure backups: etcd snapshots contain all secrets — encrypt
   snapshots, restrict access to the backup location, and test
   restores; an unencrypted snapshot is a secrets dump waiting to
   leak.
7. Harden the members: dedicated control-plane hosts, minimal OS,
   no unnecessary services, and etcd running as a non-root user where
   supported.
8. Document the recovery path: quorum loss procedures, snapshot
   restore steps, and who is authorized to perform them.

## Expected outputs

- An etcd configuration assessment: TLS, auth, encryption, network
  controls.
- Verification that secrets are encrypted at rest in etcd.
- Secured, encrypted, tested backup and restore procedures.
- A quorum-loss recovery runbook.

## Pitfalls

- Encrypting secrets in etcd but storing the encryption key
   alongside the cluster without protection: protect the key with a
   KMS.
- Backing up etcd to world-readable object storage.
- Assuming managed etcd is automatically secure: verify the
   provider's settings and your backup handling.
- Changing etcd TLS without a tested rollback: a misconfigured member
   can break quorum.

## References

- Kubernetes documentation: encrypting secret data at rest
- etcd documentation: security model and TLS setup
- CIS Kubernetes Benchmark, etcd sections
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
