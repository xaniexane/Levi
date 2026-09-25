---
skill_id: cyber_implementing_container_network_policies_with_calico
name: Container Network Policies with Calico
description: Implement Calico network policies for Kubernetes microsegmentation: default-deny with explicit allows.
risk: moderate
permissions: []
requires_confirmation: true
tags: [containers, networking]
version: 1.0.0
---
## Purpose
Kubernetes pods communicate freely by default — a compromised pod can reach every other pod, the API
server, and external destinations. Calico network policies implement microsegmentation: default-deny
traffic with explicit allow rules per workload, enforced at the host level. This playbook rolls out
Calico policies safely: audit, baseline, enforce, and maintain. Confirmation is required because
network-policy changes can sever production traffic.

## When to use
- Segmenting Kubernetes clusters to contain breaches and meet compliance (PCI DSS, HIPAA)
  network-isolation requirements.
- After incidents involving lateral movement between pods or exfiltration from workloads.
- Before production launch of multi-tenant or sensitive-data clusters.
- Replacing flat pod networking with zero-trust workload communication.
- As the network layer of container defense-in-depth (with minimal images and runtime protection).

## Prerequisites
- Calico installed as the cluster CNI or policy engine (verify version supports the policy features
  you need).
- Application communication map: which services talk to which, on what ports — from service mesh
  telemetry, flow logs, or the audit phase.
- A non-production cluster mirroring production topology for policy testing.
- Change control with fast rollback: policy misconfigurations cause outages; revert must take
  minutes.
- Cluster-admin access and a policy-as-code workflow (GitOps) for review and audit.

## Procedure
1. **Enable Calico and verify enforcement.** Confirm Calico components are healthy and policy
   enforcement is active (test with a temporary deny rule in a test namespace). Know whether you're
   using Calico NetworkPolicy (namespaced) or GlobalNetworkPolicy (cluster-wide) — plan to use both:
   global defaults, namespaced specifics.
2. **Start with audit/staged policies.** Deploy policies in audit mode first (Calico staged
   policies) that log would-deny traffic without blocking. Collect 1-2 weeks of flow data per
   namespace — this is your real communication map, better than documentation.
3. **Define the default-deny posture.** Apply a default-deny (ingress and egress)
   GlobalNetworkPolicy as the cluster baseline, with explicit exceptions for: DNS (kube-dns),
   cluster infrastructure (metrics, logging), and then per-workload allows. Default-deny is the
   goal; the allows are the work.
4. **Write explicit allow policies per workload.** For each application: allow ingress only from its
   actual clients (namespace/pod selectors + ports), allow egress only to its actual dependencies
   (databases, APIs, external endpoints by DNS/FQDN where supported). Labels are the policy language
   — enforce a labeling standard first.
5. **Handle special traffic deliberately.** DNS: allow to kube-dns only. Egress to the internet:
   default-deny with explicit FQDN allows per workload (prevents exfiltration and C2). Cluster
   services: allow health checks and metrics scraping explicitly. Each special case documented with
   justification.
6. **Test in staging with production-like traffic.** Replay realistic traffic (load tests, synthetic
   transactions) against the policy set in staging. Verify: legitimate flows pass, unauthorized
   flows are denied and logged. Fix the policies, not the tests — unexpected denies reveal
   undocumented dependencies to codify.
7. **Roll out namespace by namespace.** Enforce per namespace in waves: platform namespaces first
   (well-understood), then stateless apps, then stateful/complex apps. Each wave: enable
   enforcement, monitor deny logs intensely for 48 hours, keep rollback ready.
8. **Monitor denies as detections.** Ship Calico deny logs to the SIEM. Alert on: denied egress to
   external IPs (possible C2/exfiltration attempt), denied lateral pod-to-pod traffic (possible
   movement), and sudden deny spikes after deployments (policy drift or compromise). Deny logs are
   threat intel.
9. **Manage policies as code.** All policies in Git, peer-reviewed, applied via GitOps. Alert on
   out-of-band policy changes (kubectl-applied policies bypassing Git). Policy history is audit
   evidence and the rollback mechanism.
10. **Review and evolve quarterly.** Audit: overly broad allows (namespace-wide instead of
    pod-specific), stale policies for deleted workloads, and new workload types without policies.
    Tighten progressively — microsegmentation improves with iteration.

## Expected outputs
- Calico enforcing default-deny with explicit per-workload allow policies, managed as code.
- Staged-policy audit data justifying every allow rule.
- Namespace-by-namespace enforcement rollout with rollback capability.
- SIEM-integrated deny logging with lateral-movement and exfiltration alerting.
- Quarterly policy reviews tightening allows and removing stale rules.

## Pitfalls
- Enforcing without the audit phase: you will break DNS, health checks, or app dependencies and roll
  back the whole project. Stage first, always.
- Missing DNS: the most common self-inflicted outage — default-deny egress without a DNS allow
  breaks everything subtly.
- Label sprawl: policies keyed on inconsistent labels become unmaintainable. Standardize labels
  before writing policies.
- Overly broad allows ("allow all in namespace"): feels like progress but barely segments. Push
  toward pod-selector + port specificity.
- Out-of-band changes: emergency kubectl policy edits that never make it to Git cause drift and
  mysterious behavior. Reconcile or prohibit.

## References
- Project Calico documentation (network policies, staged policies, GlobalNetworkPolicy)
- Kubernetes NetworkPolicy documentation (API semantics Calico implements)
- NIST SP 800-207 (zero trust — microsegmentation principles)
- CIS Kubernetes Benchmark (network policy recommendations)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
