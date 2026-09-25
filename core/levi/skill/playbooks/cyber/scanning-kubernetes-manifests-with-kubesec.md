---
skill_id: cyber_scanning_kubernetes_manifests_with_kubesec
name: Scanning Kubernetes Manifests with Kubesec
description: Score Kubernetes manifests with Kubesec and enforce minimum security scores in CI and admission.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, scanning, manifests]
version: 1.0.0
---
## Purpose
Kubesec scores Kubernetes manifests against security best practices (privileged containers, host namespaces, read-only filesystems, and more). This playbook uses it to shift manifest security left: scoring in CI, setting minimum thresholds, and fixing the highest-risk patterns first.

## When to use
- CI checks on Kubernetes manifests, Helm charts, or Kustomize overlays.
- Security review of third-party charts before internal adoption.
- Baseline assessment of existing cluster workloads' manifest hygiene.
- Training developers on secure Kubernetes defaults.

## Prerequisites
- Kubesec (binary, container, or API) available to CI and developers.
- Manifest sources: raw YAML, Helm charts, or Kustomize bases.
- Agreed minimum score policy and remediation guidance per failed check.
- Admission control capability if enforcing at deploy time (e.g. Kyverno, OPA).

## Procedure
1. Run Kubesec against each manifest or rendered chart and capture the JSON score.
2. Review failures by severity: critical items (privileged, hostPath, hostNetwork) first.
3. Fix in source: drop capabilities, set readOnlyRootFilesystem, define runAsNonRoot, add resource limits.
4. Re-render Helm charts before scanning; never score unrendered templates.
5. Set a CI threshold (e.g. minimum score, zero criticals) and fail builds below it.
6. Provide developers with fix snippets per rule so the gate teaches rather than just blocks.
7. For existing clusters, scan live workloads' manifests and prioritize remediation by exposure.
8. Consider admission-time enforcement so bypassing CI does not bypass the policy.
9. Combine Kubesec scoring with namespace-level Pod Security admission for defense in depth.
10. Track score trends per team; declining scores indicate process drift.
11. Review Kubesec's scoring rules on upgrade; new checks can fail previously passing manifests.

## Expected outputs
- Per-manifest Kubesec scores with before/after remediation evidence.
- CI gate configuration with threshold policy.
- Developer guidance mapping each failed check to a fix.
- Per-team score trend dashboard.
- Kubesec version and rule-change log.
- Exception register for legitimately privileged workloads.

## Pitfalls
- Scores are heuristic; a high score does not guarantee a secure workload.
- Some workloads legitimately need privileges; handle via documented exceptions, not ignored failures.
- Chart defaults are often insecure; always review values, not just the chart's reputation.
- Kubesec checks a point in time; runtime policies (Pod Security Standards) provide defense in depth.
- Kubesec does not evaluate network policies or RBAC; pair it with cluster-level checks.
- Score thresholds set too high on day one block all delivery; phase them in.
- Init containers and ephemeral containers need the same scrutiny as main containers.
- GitOps drift means the scanned manifest may not match the live object; verify against the cluster.

## References
- Kubesec project documentation.
- Kubernetes documentation: Pod Security Standards.
- NIST SP 800-190, Application Container Security Guide.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
