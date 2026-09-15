---
skill_id: cyber_detecting_privilege_escalation_in_kubernetes_pods
name: Detecting Privilege Escalation in Kubernetes Pods
description: Detect container-breakout and in-cluster privilege escalation via Kubernetes audit logs.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, container, detection]
version: 1.0.0
---
## Purpose

Compromised pods are the beachhead; privilege escalation — to node root, to cluster-admin — is the objective. This playbook uses Kubernetes audit logs and runtime telemetry to detect escalation: suspicious RBAC changes, pod-spec abuse, host-namespace access, and node-level breakout indicators.

## When to use

- You run production Kubernetes and need escalation detection beyond image scanning.
- A pod compromise is suspected and you need to check for cluster-wide escalation.
- Threat hunting for container-escape techniques in your clusters.
- Compliance requires monitoring of privileged pod and RBAC changes.

## Prerequisites

- Kubernetes audit logging enabled (audit policy capturing RBAC, pod, and exec operations) shipped to your SIEM.
- Runtime security telemetry (Falco, Tetragon, or equivalent) for in-pod syscall/process visibility.
- Baseline: which service accounts/namespaces legitimately use privileged pods, hostPath, hostNetwork.
- RBAC inventory: cluster-admin bindings, wildcard roles, and their owners.

## Procedure

1. Audit RBAC changes as the primary escalation path. Alert on: new ClusterRoleBindings (especially to cluster-admin or wildcard roles), RoleBindings granting secrets/configmap access in kube-system, creation of service accounts with excessive bindings, and modifications to existing privileged roles. RBAC changes outside GitOps pipelines or change windows are high severity — legitimate RBAC changes should be code-reviewed and traceable.
2. Detect pod-spec abuse. Alert on pods/admission requests with: privileged: true, hostPID/hostNetwork/hostIPC, hostPath volumes (especially sensitive paths like /var/run/docker.sock, /etc, /proc), allowPrivilegeEscalation: true with added capabilities (SYS_ADMIN, SYS_PTRACE, NET_ADMIN), and new capabilities outside your baseline. Pair with admission-controller (OPA/Kyverno) deny logs — blocked attempts are attack signal too.
3. Watch for node-targeting behaviors. From runtime telemetry: processes in pods accessing node filesystems via hostPath, unexpected nsenter-like namespace transitions, attempts to read cloud instance-metadata credentials from pods, and kubelet API abuse. From audit logs: exec into privileged pods, especially followed by host-filesystem access patterns.
4. Detect service-account token abuse. Alert on: service-account tokens used from outside the cluster (token exfiltrated), tokens accessing resources beyond their namespace scope, and automount tokens on pods that don't need API access. Correlate token-use anomalies with the pod compromise timeline.
5. Scope cluster-wide on any confirmed escalation. A node-root or cluster-admin compromise means: every workload on affected nodes is suspect, all service-account tokens on those nodes are burned, and etcd secrets may be exposed. Plan node rotation, token revocation, and secret rotation — not just pod deletion.
6. Harden the escalation paths: enforce Pod Security Standards (restricted), require admission control denying privileged/host namespaces, scope RBAC to least privilege with regular reviews, disable automount where unneeded, and isolate sensitive namespaces. Detection catches escalation; admission control prevents it.

## Expected outputs

- K8s audit-log detections: RBAC changes, privileged pod-spec, exec anomalies, token abuse.
- Runtime detections: hostPath abuse, namespace transitions, metadata-credential access.
- Admission-control policy (deny privileged/host namespaces) with deny-log monitoring.
- Cluster-escalation response plan: node rotation, token/secret revocation procedures.

## Pitfalls

- Audit logs without a proper audit policy miss the events you need — verify policy captures RBAC and pod-spec verbs.
- Legitimate platform tooling (CNI, CSI, monitoring) uses privileged pods — baseline by service account, not just flags.
- exec into pods is normal for debugging; alert on exec into privileged pods or unusual images, not all exec.
- Deleting a compromised pod without rotating its service-account token leaves the attacker authenticated.
- Multi-cluster environments need per-cluster baselines — a rule tuned for dev will misfire in prod.

## References

- Kubernetes documentation: audit logging, RBAC, Pod Security Standards; MITRE ATT&CK T1611 (Escape to Host), T1609 (Container Administration Command) — https://attack.mitre.org/techniques/T1611/; NIST SP 800-190 (container security)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
