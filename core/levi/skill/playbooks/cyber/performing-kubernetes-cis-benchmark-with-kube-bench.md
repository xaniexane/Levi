---
skill_id: cyber_performing_kubernetes_cis_benchmark_with_kube_bench
name: Kubernetes CIS Benchmark with kube-bench
description: Audit Kubernetes clusters against the CIS benchmark and remediate findings.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, benchmark, hardening]
version: 1.0.0
---
# Kubernetes CIS Benchmark with kube-bench

## Purpose

kube-bench checks a Kubernetes cluster's configuration against the CIS
Kubernetes Benchmark: API server flags, etcd settings, kubelet
configuration, and RBAC hygiene. This playbook runs the assessment and
turns failures into hardened configuration.

## When to use

- Hardening a new cluster before production workloads land.
- Compliance evidence for CIS-benchmark requirements.
- Validating managed-service defaults (EKS, AKS, GKE) against the
  benchmark.
- Post-incident verification of control-plane configuration.

## Prerequisites

- kube-bench run with access to control-plane components; on managed
  services, run the node check and document which control-plane checks
  are the provider's responsibility.
- Knowledge of which CIS version matches your Kubernetes version
  (kube-bench selects benchmark version by detection or flag).
- A change process for control-plane flags: they often require
  node or component restarts.

## Procedure

1. Run kube-bench on a control-plane node (`kube-bench run
   --targets master`) and on a worker (`--targets node`); capture
   dated JSON output for evidence.
2. Triage failures by impact: insecure API server flags
   (`--insecure-port`, anonymous auth enabled), etcd without TLS or
   client-cert auth, and kubelet anonymous access outrank
   informational items.
3. Remediate control-plane flags via your cluster's configuration
   management (kubeadm config, managed-service settings) — never by
   hand-editing static pod manifests on a single node.
4. Harden the kubelet: disable anonymous auth, enforce webhook
   authorization, set `--protect-kernel-defaults`, and restrict the
   read-only port.
5. Address etcd findings: enforce TLS for peer and client traffic with
   client-certificate authentication, and verify data-at-rest
   encryption for secrets (`--encryption-provider-config`).
6. Review RBAC separately: kube-bench checks configuration, not
   authorization — audit cluster-admin bindings and wildcard roles in
   the same pass.
7. Handle managed-service gaps honestly: document checks that fail
   because the provider controls the component, and verify the
   provider's compliance attestation covers them.
8. Re-run and trend: schedule kube-bench in CI for cluster
   configuration changes and keep dated reports as audit evidence.

## Expected outputs

- Dated kube-bench reports (master and node) mapped to CIS sections.
- Remediation records with the configuration changes made.
- Documented provider-responsibility exceptions for managed services.
- A recurring assessment schedule.

## Pitfalls

- Editing static pod manifests by hand: the next control-plane
   upgrade reverts them — fix the source configuration.
- Treating a passing score as "secure": the benchmark covers
   configuration, not workload or RBAC flaws.
- Running the wrong benchmark version for your Kubernetes release.
- Ignoring node-level findings because "the control plane passed."

## References

- CIS Kubernetes Benchmark (CIS WorkBench)
- kube-bench documentation (aquasecurity.github.io/kube-bench)
- Kubernetes documentation: securing the cluster
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
