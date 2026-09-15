# Benchmarking Kubernetes with kube-bench

## Purpose

Run kube-bench — the automated CIS Kubernetes Benchmark checker — against cluster nodes
and control-plane components to produce a repeatable, control-by-control hardening
assessment of the Kubernetes installation itself.

## When to use

- Baseline hardening assessments of new or existing clusters.
- Pre-production sign-off for platform teams ("does this cluster meet CIS Level 1?").
- Regression checks after Kubernetes upgrades — upgrades reset flags and re-add
  components.
- Complementing the RBAC-focused audits with control-plane and kubelet configuration
  coverage.

See also: auditing-kubernetes-cluster-rbac.md, auditing-cloud-with-cis-benchmarks.md

## Prerequisites

- Written authorization and a defined scope: cluster name(s) in bounds.
- kubectl access sufficient to create Jobs (kube-bench typically runs as a Job with
  hostPath access to node config); coordinate with the platform team — kube-bench reads
  sensitive host paths.
- The CIS Kubernetes Benchmark version matching your Kubernetes version (kube-bench
  release notes map versions); agree Level 1 vs Level 2 scope with the owner.
- A maintenance-adjacent window for managed clusters — kube-bench is read-only, but run
  it when the platform team is available to discuss findings.

## Procedure

1. **Match kube-bench to the cluster version.**
   - Check `kubectl version` and pick the kube-bench release whose default config targets
     that Kubernetes/CIS version (`kube-bench --version` and the release notes).
   - A version mismatch produces misleading PASS/FAIL — this is the most common
     kube-bench error.

2. **Deploy kube-bench as a Job.**
   - Use the upstream job manifests (`job.yaml` for a single node test, or the
     node/master job split for self-hosted control planes).
   - For managed clusters (EKS/AKS/GKE), control-plane components are the provider's
     responsibility — run the node-target checks and document which controls are
     provider-owned.

3. **Run the node checks.**
   - `kubectl apply -f job-node.yaml`, then read logs: `kubectl logs job/kube-bench-node`.
   - Alternatively run the binary directly on a node: `kube-bench run --targets node`.

4. **Run the control-plane checks (self-hosted only).**
   - `kube-bench run --targets master` (older releases) or the etcd/controlplane/policy
     target split in newer releases — check `--help` for the installed version's targets.
   - These verify API server, scheduler, controller-manager, and etcd flags.

5. **Triage every FAIL.**
   - For each failure, determine: true misconfiguration, provider-managed (managed
     clusters), compensating control, or accepted risk.
   - Read the check's `remediation` text in the output — kube-bench prints the exact flag
     or config change expected; verify it against the CIS Benchmark text before applying.

6. **Verify remediations manually.**
   - After the platform team applies fixes (e.g., `--anonymous-auth=false`,
     `--authorization-mode=RBAC`, kubelet `--read-only-port=0`), re-run kube-bench to
     confirm the check flips to PASS.
   - Spot-check a sample of PASS results too — kube-bench checks config presence, not
     semantic correctness, in a few edge cases.

7. **Handle the manual checks.**
   - kube-bench marks some controls `[MANUAL]` — these require human verification (e.g.,
     image provenance policies, certain admission controls).
   - Work through each manual check with the platform team and record evidence; they are
     not optional.

8. **Score, trend, and report.**
   - Record pass/fail per CIS section, the kube-bench version, and the CIS Benchmark
     version.
   - Compare against the previous run to show drift; investigate regressions first.

## Key tools & commands

- `kube-bench run --targets node` / `--targets etcd,controlplane,policies` — direct runs
  (target names vary by release; check `--help`).
- `kubectl apply -f job.yaml && kubectl logs job/kube-bench` — the standard in-cluster
  execution pattern.
- `kube-bench --version` — pin and record for reproducibility.
- CIS Kubernetes Benchmark PDF (Center for Internet Security) — the normative text behind
  each check.

## Expected outputs

- kube-bench output logs (versioned) for node and control-plane targets.
- Triage register: each FAIL → true positive / provider-managed / compensating /
  accepted risk, with evidence.
- Manual-check verification notes.
- Section scores and trend vs. the previous run.

## Pitfalls

- Version mismatch between kube-bench, Kubernetes, and the CIS Benchmark — always align
  all three.
- Running only node checks on a self-hosted cluster and declaring victory — the
  control-plane flags are where the critical failures live.
- Treating provider-managed FAILs on EKS/AKS/GKE as your findings — document them as
  provider-owned with the shared-responsibility reference.
- Applying kube-bench's remediation text blindly — some remediations break legitimate
  workflows (e.g., disabling the read-only kubelet port affects monitoring); test in
  non-production first.

## References

- kube-bench project documentation (Aqua Security) — install, targets, config.
- CIS Kubernetes Benchmark (Center for Internet Security, via CIS WorkBench).
- Kubernetes documentation: kubelet and kube-apiserver flag references.
- MITRE ATT&CK: T1609 (Container Administration Command), T1078 (Valid Accounts).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
