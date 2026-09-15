---
skill_id: cyber_scanning_iac_and_images_with_trivy
name: Scanning IaC and Images with Trivy
description: Scan Terraform, Kubernetes manifests, and Dockerfiles with Trivy misconfiguration checks alongside image scans.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, iac, trivy]
version: 1.0.0
---
## Purpose
Misconfigurations in infrastructure-as-code ship the vulnerabilities that image scanners never see: public buckets, privileged pods, open security groups. This playbook extends Trivy beyond images to IaC scanning, giving one workflow that covers both the workload and the infrastructure it declares.

## When to use
- IaC pull-request checks for Terraform, CloudFormation, or Kubernetes manifests.
- Pre-deployment review of Helm-rendered or Kustomize-built manifests.
- Compliance evidence collection for infrastructure configuration.
- After a misconfiguration-driven incident, to prevent recurrence.

## Prerequisites
- Trivy with misconfiguration scanning enabled and current policies.
- Repository access to the IaC and manifest sources.
- Baseline of existing findings so new PRs are judged on deltas.
- Policy decisions: which checks fail the build vs warn.

## Procedure
1. Scan the IaC directory: `trivy config --severity HIGH,CRITICAL ./terraform`.
2. Render Helm charts or Kustomize overlays first, then scan the rendered manifests.
3. Scan Dockerfiles in the same run to catch image-build misconfigurations.
4. Triage by reachability and exposure: a privileged pod in production beats a warning in a dev overlay.
5. Fix in source: restrictive security contexts, non-public storage, encrypted volumes, dropped capabilities.
6. Suppressions go in code with justification comments and expiry, never silent global ignores.
7. Gate merges on new high/critical findings while grandfathering existing ones with remediation plans.
8. Combine with image scanning in the same pipeline for full coverage of code, image, and config.
9. Scan Terraform plan output as well as source; some values only exist at plan time.
10. Audit inline suppressions regularly; they accumulate into blind spots.
11. Run the scan against the default branch on a schedule to catch drift outside PRs.

## Expected outputs
- IaC scan reports per change with delta vs baseline.
- Remediated IaC with rescan evidence.
- Suppression log with justifications and expiries.
- Plan-time scan results complementing source scans.
- Suppression audit log with justifications.
- Scheduled default-branch scan history.

## Pitfalls
- Scanning unrendered Helm templates produces noise; always render first.
- Default policies may not match your risk model; customize severity and checks.
- Grandfathered findings without owners never get fixed; assign and date them.
- Config scanning complements but does not replace runtime posture checks.
- Inline suppressions without expiry become permanent; audit them on a cadence.
- Plan-time values can differ from source; scanning only source misses real configuration.
- Custom policies need versioning alongside the code they check.
- Policy-as-code changes need the same peer review as application code.

## References
- Aqua Trivy documentation: misconfiguration scanning.
- CIS Benchmarks for Terraform/AWS/Azure as policy reference.
- NIST SP 800-190, Application Container Security Guide.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
