---
skill_id: cyber_implementing_pod_security_admission_controller
name: Implementing Pod Security Admission Controller
description: Configure and operate the Kubernetes Pod Security Admission controller — namespace labels, version pinning, exemption handling, and CI integration.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, admission-control, hardening]
version: 1.0.0
---
## Purpose

Operationalize Pod Security Admission (PSA) — the built-in Kubernetes admission controller that replaced PodSecurityPolicy — as a dependable guardrail: namespaces labeled with enforce, audit, and warn modes at the appropriate Pod Security Standard level, versions pinned for upgrade safety, exemptions governed, and developers getting feedback in CI before the API server rejects their pods.

## When to use

- Enforcing Pod Security Standards without third-party admission webhooks.
- Replacing deprecated PodSecurityPolicy (removed in Kubernetes 1.25+) with the supported mechanism.
- Providing baseline guardrails in clusters where full policy engines (Gatekeeper/Kyverno) are overkill or a second layer.
- Meeting CIS Benchmark expectations for workload security configuration.
- Standardizing namespace security posture across many clusters.

## Prerequisites

- Kubernetes 1.23+ with PSA enabled (built-in and enabled by default; verify it's not disabled via `--disable-admission-plugins`).
- Namespace inventory classified by required policy level (restricted, baseline, privileged).
- List of system/privileged workloads needing exemptions (CNI, CSI, monitoring, service mesh components).
- RBAC control over namespace labeling — anyone who can relabel namespaces can bypass enforcement.
- CI pipeline integration point for pre-deploy policy checks.

## Procedure

1. **Verify PSA is active.** Check the API server admission plugins and confirm PSA responds:
   ```bash
   kubectl label --dry-run=server namespace default \
     pod-security.kubernetes.io/enforce=restricted
   ```
   If your managed Kubernetes offering disables or restricts admission plugins, confirm PSA availability before planning around it.
2. **Baseline with audit and warn modes.** Label every namespace with `audit=restricted` and `warn=restricted` (plus `audit-version`/`warn-version` pinned). Collect violations over a full release cycle via audit logs and user-facing warnings. Categorize each violation: fix the manifest, or document a genuine exemption.
3. **Fix workloads toward restricted.** Update manifests for the common restricted requirements: `runAsNonRoot`, `seccompProfile.type: RuntimeDefault`, `allowPrivilegeEscalation: false`, dropping all capabilities. Do this in the application repositories with developer ownership — platform teams fixing app manifests doesn't scale.
4. **Apply enforce labels per namespace.** Set `pod-security.kubernetes.io/enforce` to the strictest level each namespace sustains, with the version pinned:
   ```bash
   kubectl label namespace payments \
     pod-security.kubernetes.io/enforce=restricted \
     pod-security.kubernetes.io/enforce-version=v1.30
   ```
   New namespaces get `enforce=restricted` by default via your namespace-provisioning automation; lowering it requires an approved exception.
5. **Pin versions and plan upgrades.** Never use `latest` for enforce/audit/warn versions in production — a cluster upgrade could introduce new checks that block running workloads' updates. Test new policy versions in non-production, then bump pins deliberately per namespace tier.
6. **Govern exemptions tightly.** Exempt namespaces (kube-system and equivalents) get documented justification, owner, and review date. Prefer exempting specific namespaces over cluster-wide configuration, and never exempt application namespaces permanently. Re-audit exemptions quarterly.
7. **Lock down the bypass paths.** RBAC-restrict who can add or change `pod-security.kubernetes.io/*` labels (typically cluster-admins only, via a dedicated ClusterRole). Monitor label changes in audit logs — a namespace silently relabeled from `restricted` to `privileged` is a policy bypass that PSA itself won't flag.
8. **Shift feedback left.** Add PSS checks to CI (kube-linter, checkov, or `kubectl label --dry-run=server`) so developers see violations in pull requests. Admission denial at deploy time should be rare because CI caught it first. Ship PSA denials and warnings to the SIEM as workload-hardening telemetry.

## Expected outputs

- Namespace label matrix (enforce/audit/warn + pinned versions) managed as code.
- Application manifests remediated toward restricted; exception register with reviews.
- RBAC restrictions on policy labels with audit-log monitoring of changes.
- CI checks providing pre-deploy feedback; SIEM telemetry on denials/warnings.

## Pitfalls

- **Unpinned `latest` versions.** The most common PSA operational failure: a minor upgrade changes policy behavior and blocks deployments fleet-wide. Pin everything.
- **Label-change bypass.** PSA enforces based on namespace labels; RBAC that lets developers relabel their namespaces voids the control. Guard the labels as carefully as the policies.
- **Enforcing before the audit phase.** Blocking legitimate system workloads (DNS autoscalers, mesh sidecar injectors, monitoring agents) on day one creates pressure to disable PSA entirely. Audit first, always.
- **Assuming exemptions are static.** System components change across upgrades; an exemption valid for the old monitoring agent may be unnecessary — or insufficient — for the new one. Re-validate per upgrade.
- **PSA as the only admission control.** PSA covers pod security contexts well but not image provenance, registry allowlists, or custom organizational policy. Layer Kyverno/Gatekeeper where those matter.

## References

- Pod Security Admission documentation — https://kubernetes.io/docs/concepts/security/pod-security-admission/
- Pod Security Standards — https://kubernetes.io/docs/concepts/security/pod-security-standards/
- Kubernetes dynamic admission control — https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
- CIS Kubernetes Benchmark — https://www.cisecurity.org/cis-benchmarks
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
