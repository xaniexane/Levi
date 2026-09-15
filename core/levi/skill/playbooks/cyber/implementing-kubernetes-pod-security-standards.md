---
skill_id: cyber_implementing_kubernetes_pod_security_standards
name: Implementing Kubernetes Pod Security Standards
description: Enforce the Kubernetes Pod Security Standards (Privileged, Baseline, Restricted) via Pod Security Admission to eliminate privileged and risky pod configurations.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, hardening, admission-control]
version: 1.0.0
---
## Purpose

Stop the most common Kubernetes privilege-escalation paths at admission time. The Pod Security Standards (PSS) define three policies — Privileged (unrestricted), Baseline (prevents known privilege escalations), and Restricted (hardened, follows best practices) — and Pod Security Admission enforces them per namespace, so a `privileged: true` pod or a container running as root with a writable hostPath simply never gets created.

## When to use

- Hardening clusters to CIS Kubernetes Benchmark expectations.
- Preventing container-escape and host-compromise primitives (privileged pods, hostPID/hostNetwork, dangerous capabilities).
- Multi-tenant or shared clusters where tenants must not affect each other or the nodes.
- Meeting compliance requirements for least-privilege workload execution.
- After an incident involving a compromised pod escalating to the node.

## Prerequisites

- Kubernetes 1.23+ (Pod Security Admission built in; PSS replaced PodSecurityPolicy, removed in 1.25).
- Namespace inventory with classification: which namespaces can tolerate Restricted, which need Baseline exemptions.
- List of legitimate privileged workloads (CNI, CSI, monitoring agents, service meshes) that will need explicit exemptions.
- Cluster-admin rights to set namespace labels, and a test namespace for dry runs.
- Audit logging enabled so you can measure violations before enforcing.

## Procedure

1. **Audit first with warn mode.** Label namespaces to audit all three levels without blocking:
   ```bash
   kubectl label namespace <ns> \
     pod-security.kubernetes.io/audit=restricted \
     pod-security.kubernetes.io/warn=restricted
   ```
   Collect warnings for a full release cycle. Every violation is either a workload to fix or an exemption to document — decide each deliberately.
2. **Fix what you can.** The common Restricted requirements: `runAsNonRoot: true`, `seccompProfile.type: RuntimeDefault`, `allowPrivilegeEscalation: false`, dropping ALL capabilities, and `readOnlyRootFilesystem` where feasible. Most application pods can meet Restricted with manifest changes; fix them in the app repos, not with exemptions.
3. **Set enforce levels per namespace.** Apply the strictest level each namespace tolerates:
   ```bash
   kubectl label namespace prod \
     pod-security.kubernetes.io/enforce=restricted \
     pod-security.kubernetes.io/enforce-version=latest
   ```
   Default new namespaces to `restricted`; require a documented exception (owner, justification, expiry) to lower it.
4. **Exempt system namespaces narrowly.** kube-system and monitoring namespaces often need Baseline or Privileged for CNI/CSI/agents. Exempt by namespace, never cluster-wide, and pin exemptions to specific service accounts or controllers where the admission version supports it. Review exemptions quarterly.
5. **Pin the policy version.** Set `enforce-version` (e.g., `v1.30`) rather than `latest` so a cluster upgrade does not suddenly change admission behavior under running workloads. Upgrade the pinned version deliberately after testing.
6. **Block the bypass paths.** PSS only governs pods; also restrict who can create the exempting resources: RBAC-limit namespace label changes, `use` of privileged PodSecurityPolicy remnants, and direct node access. An attacker with namespace-admin can relabel their way out — scope RBAC accordingly.
7. **Integrate with CI.** Add kube-linter, checkov, or conftest checks to pipelines so non-compliant manifests fail before they reach the cluster. Admission is the last line, not the first.
8. **Monitor violations as signals.** Ship Pod Security Admission warnings and denials to the SIEM. A denied privileged-pod creation in a production namespace is worth an alert — it is either a misconfigured deploy or someone probing for escape primitives.

## Expected outputs

- Namespace labeling matrix (enforce/audit/warn levels + pinned versions) with exception register.
- Application manifests updated to meet Restricted where possible.
- CI checks blocking non-compliant pod specs.
- SIEM detections on admission denials and warnings.
- Quarterly exemption review records.

## Pitfalls

- **Enforcing Restricted on day one.** Legitimate workloads (logging agents, meshes, some databases) will fail and teams will demand the control be disabled. Audit → fix → enforce, in that order.
- **Exempting whole namespaces permanently.** A permanent `privileged` exemption on a namespace that later hosts application pods quietly voids the control. Time-box exemptions and re-audit.
- **Forgetting the RBAC bypass.** Anyone who can label namespaces or edit the exempted controllers bypasses PSS entirely. The admission control is only as strong as the RBAC around it.
- **Version drift with `latest`.** A minor cluster upgrade can introduce new checks that block previously fine pods. Pin versions and test upgrades.
- **Assuming PSS covers everything.** PSS does not restrict hostPath volumes beyond the obvious, image provenance, or network policy. Layer it with image signing, admission policies (Kyverno/Gatekeeper), and network policy.

## References

- Kubernetes Pod Security Standards — https://kubernetes.io/docs/concepts/security/pod-security-standards/
- Pod Security Admission documentation — https://kubernetes.io/docs/concepts/security/pod-security-admission/
- CIS Kubernetes Benchmark — https://www.cisecurity.org/cis-benchmarks
- MITRE ATT&CK T1611 (Escape to Host) — https://attack.mitre.org/techniques/T1611/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
