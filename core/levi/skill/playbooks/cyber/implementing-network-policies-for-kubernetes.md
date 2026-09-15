---
skill_id: cyber_implementing_network_policies_for_kubernetes
name: Implementing Network Policies for Kubernetes
description: Apply Kubernetes-native NetworkPolicy for namespace isolation and workload least-privilege, CNI-agnostic, with a safe default-deny rollout.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, network, segmentation]
version: 1.0.0
---
## Purpose

Enforce least-privilege pod networking using the portable Kubernetes NetworkPolicy API — no vendor CNI required. This playbook takes a cluster from flat networking to explicit allowlists: default-deny baselines, per-workload ingress/egress rules, DNS handling, and policy-as-code practices that work on any conformant CNI (Calico, Cilium, Antrea, kube-router) while noting where to reach for CNI-specific extensions.

## When to use

- Establishing baseline workload segmentation on any Kubernetes cluster.
- Meeting compliance expectations for network segmentation without committing to a specific CNI vendor's policy CRDs.
- Multi-namespace clusters where teams' workloads must not reach each other by default.
- Egress control for data-tier and batch workloads (block internet egress except where needed).
- As the portable foundation before layering CNI-specific advanced policy (FQDN egress, L7 rules).

## Prerequisites

- A CNI that enforces NetworkPolicy (verify — kubenet and some minimal CNIs do not; check with a test deny policy, not documentation claims).
- Service dependency map per namespace: who calls whom, on which ports.
- Namespace and label conventions suitable for policy selectors.
- Non-production environment for policy development.
- Flow visibility (CNI flow logs, Hubble, or packet capture) to build policies from observed traffic.

## Procedure

1. **Verify enforcement works.** Apply a test default-deny policy in a scratch namespace and confirm traffic actually stops. Some CNIs claim support with caveats (egress-only, no named ports). Do not build a segmentation program on an unenforced API.
2. **Establish namespace isolation.** Apply a default-deny-ingress policy per namespace that blocks cross-namespace traffic while allowing intra-namespace communication:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: deny-cross-namespace
     namespace: payments
   spec:
     podSelector: {}
     policyTypes: [Ingress]
     ingress:
     - from:
       - podSelector: {}   # same-namespace only
   ```
   Roll out namespace by namespace, non-production first.
3. **Add default-deny-all, then explicit allows.** Once isolation holds, move namespaces to full default-deny (ingress + egress) and write per-workload allow policies from observed flows: ingress from specific podSelectors/namespaceSelectors on specific ports; egress to kube-dns (port 53), the API server, and declared dependencies only.
4. **Handle DNS and platform traffic explicitly.** Every egress-restricted workload needs DNS (UDP/TCP 53 to the kube-dns service) and, where applicable, API server access. Missing DNS rules are the most common self-inflicted outage — verify name resolution works before considering a namespace done.
5. **Write egress policies for data protection.** For databases, batch jobs, and sensitive workloads, allow egress only to declared dependencies and deny everything else — particularly the internet and cloud metadata endpoints. Where the CNI supports it, add FQDN-based egress rules for required external APIs; otherwise use narrow IP/CIDR allows with a documented refresh process.
6. **Codify with the application.** Keep NetworkPolicy manifests in the same repository as the workload, reviewed in the same pull requests. Add CI checks (kube-linter, conftest, or a custom check) requiring a network policy for every Deployment/StatefulSet — no policy, no deploy.
7. **Test policy behavior in CI and staging.** Use a policy simulator or staging-cluster tests that assert allowed flows succeed and representative denied flows fail. Network policy misconfigurations are silent until they break production at 2 a.m.; tests make them loud in the pipeline.
8. **Monitor denials and drift.** Where the CNI exposes policy-denial logs or metrics, ship them to the SIEM and alert on denied lateral attempts. Re-audit policies quarterly against actual flow logs — services evolve, and stale allows accumulate.

## Expected outputs

- Verified NetworkPolicy enforcement on the cluster's CNI.
- Per-namespace default-deny baselines with per-workload allow policies in version control.
- Documented DNS/platform-traffic handling.
- CI gates requiring network policies for new workloads, with behavior tests.
- Denial telemetry feeding the SIEM with lateral-movement alerts.

## Pitfalls

- **Assuming the CNI enforces policy.** The API existing is not enforcement. Test it; several lightweight CNIs silently ignore policies.
- **Forgetting DNS.** The single most common breakage. Allow kube-dns explicitly in every egress policy before enforcing.
- **Named ports and selectors mismatch.** Policies select pods by label — a label rename or a selector typo silently leaves workloads unprotected or broken. Lint selectors in CI.
- **Egress to the internet via IP allows that rot.** External API IPs change; stale CIDR allows either break the app or get widened to 0.0.0.0/0 in a panic. Prefer FQDN-aware CNI extensions where available.
- **Policy only on paper for hostNetwork pods.** Pods using host networking bypass pod-level policy entirely. Restrict hostNetwork via Pod Security Standards and treat any exception as a segmentation gap.

## References

- Kubernetes NetworkPolicy concepts — https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Kubernetes: declare network policy (task walkthrough) — https://kubernetes.io/docs/tasks/administer-cluster/declare-network-policy/
- CIS Kubernetes Benchmark — https://www.cisecurity.org/cis-benchmarks
- MITRE ATT&CK T1021 (Remote Services) lateral-movement context — https://attack.mitre.org/techniques/T1021/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
