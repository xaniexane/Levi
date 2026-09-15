---
skill_id: cyber_implementing_kubernetes_network_policy_with_calico
name: Implementing Kubernetes Network Policy with Calico
description: Enforce Kubernetes network segmentation with Calico — default-deny policies, staged rollout, and observability before blocking production traffic.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, network, segmentation, calico]
version: 1.0.0
---
## Purpose

Turn the Kubernetes cluster's flat pod network into explicit, least-privilege connectivity using Calico network policy. Starting from a default-deny posture, you define which pods may talk to which — by labels, namespaces, and ports — with Calico's richer policy model (ordered rules, GlobalNetworkPolicy, egress controls, DNS-aware rules) backing the standard Kubernetes NetworkPolicy API.

## When to use

- Meeting compliance requirements for workload segmentation (PCI DSS, SOC 2) in Kubernetes.
- Containing lateral movement after a pod compromise — the flat network is an attacker's highway.
- Multi-tenant clusters where namespaces must be isolated from each other.
- Egress control: preventing pods from reaching the internet, metadata endpoints, or unexpected destinations.
- Standardizing network policy as code alongside application manifests.

## Prerequisites

- Calico installed as the CNI (or in policy-only mode alongside another CNI) with `calicoctl` available.
- Complete service-dependency map: which pods call which, on what ports — build from flow logs, not assumptions.
- Labels and namespaces designed for policy selection; policy keyed on chaotic labels becomes unmaintainable.
- A non-production cluster (or namespace) for policy development and testing.
- Flow-log visibility (Calico flow logs, or `kubectl` + packet captures) to validate behavior before enforcing.

## Procedure

1. **Enable flow visibility first.** Turn on Calico flow logs and collect a week of pod-to-pod and pod-to-external traffic. Export to your SIEM or a log aggregator. This baseline is the raw material for every policy you write — and the evidence you show auditors.
2. **Apply default-deny per namespace.** Start with namespace-scoped default-deny ingress and egress policies:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: default-deny-all
   spec:
     podSelector: {}
     policyTypes: [Ingress, Egress]
   ```
   Apply to one non-critical namespace first. Expect breakage — that is the point of staging.
3. **Write allow policies from the baseline.** For each workload, create policies selecting its pods by label and allowing only observed, necessary flows: ingress from specific source labels/ports, egress to specific destinations (including kube-dns on 53 and the API server). Prefer Calico `NetworkPolicy`/`GlobalNetworkPolicy` where you need ordered deny rules, egress to FQDNs, or apply-on-forward semantics.
4. **Handle platform traffic explicitly.** Allow DNS (UDP/TCP 53 to kube-dns), Kubernetes API access for controllers that need it, and node-to-pod health checks. Forgetting DNS is the classic day-one outage — pods resolve nothing and everything fails cryptically.
5. **Stage the rollout namespace by namespace.** Move from dev to staging to production namespaces, running each in enforce mode for several days while watching policy-denied flow logs. Keep a fast rollback path: label-based policy removal or a temporary allow rule with a short TTL and an incident ticket.
6. **Add GlobalNetworkPolicy for cluster-wide guardrails.** Use Calico global policies for rules that span namespaces: deny egress to cloud metadata endpoints (169.254.169.254) except from approved workloads, block known-bad destinations, enforce that only the ingress namespace accepts external traffic.
7. **Codify policies with applications.** Store network policies in the same repos as the workloads they protect, reviewed in the same PRs. Add CI checks (kube-linter, conftest) that every deployment ships with a network policy.
8. **Monitor denials as detections.** Ship denied-flow logs to the SIEM and alert on patterns: denied egress to the internet from a data-tier pod, denied lateral attempts between namespaces, spikes in denies after a deployment. Policy denies are free intrusion telemetry.

## Expected outputs

- Default-deny policies in every namespace, with per-workload allow policies in version control.
- Calico GlobalNetworkPolicies for metadata-endpoint protection and cluster-wide guardrails.
- Flow-log pipeline feeding the SIEM with denial-based detections.
- Staged rollout record and rollback procedures.
- CI checks requiring network policies for new workloads.

## Pitfalls

- **Denying kube-dns.** The number-one self-inflicted outage. Explicitly allow DNS before enforcing egress deny.
- **Label sprawl.** Policies selecting `app: foo` break when teams rename labels. Govern the label taxonomy or policies rot.
- **Forgetting host-network and system namespaces.** kube-system components, CNI daemons, and monitoring agents need carefully scoped exceptions — blanket-allowing kube-system reopens the flat network.
- **Egress to FQDN without DNS policy.** Calico can filter egress by domain, but it depends on DNS visibility; misconfigured DNS policy silently breaks the mapping.
- **Policy as a one-time project.** Every new microservice without a policy either breaks (if default-deny holds) or gets a panicked allow-all. Make policy part of the service scaffolding.

## References

- Calico network policy documentation — https://docs.tigera.io/calico/latest/network-policy/
- Kubernetes NetworkPolicy concepts — https://kubernetes.io/docs/concepts/services-networking/network-policies/
- CIS Kubernetes Benchmark (network policy controls) — https://www.cisecurity.org/cis-benchmarks
- MITRE ATT&CK T1048-adjacent lateral movement considerations; container escape T1611 — https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
