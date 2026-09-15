---
skill_id: cyber_performing_container_security_scanning_with_trivy
name: Container Security Scanning with Trivy
description: Scan container images, filesystems, and IaC with Trivy and operationalize findings in CI/CD.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, vulnerability-management, devsecops]
version: 1.0.0
---

## Purpose

Trivy scans container images, filesystems, repositories, and infrastructure-as-code for known vulnerabilities, misconfigurations, and exposed secrets in a single fast tool. This playbook covers deploying Trivy effectively: scan targets and modes, integrating it as a CI/CD gate, triaging its output into actionable work, and keeping the vulnerability database fresh. The goal is a scanning practice developers trust — accurate enough to act on, quiet enough not to be ignored.

## When to use

- Adding vulnerability scanning to a container build pipeline.
- Auditing images already in a registry for known CVEs.
- Checking IaC (Dockerfiles, Kubernetes manifests, Terraform) for misconfigurations before deployment.
- Investigating whether a published CVE affects your deployed images.
- Evaluating scanner accuracy or comparing tools during a tooling selection.

## Prerequisites

- Trivy installed on CI runners and analyst workstations, with network access to its vulnerability database (or an offline DB mirror for air-gapped environments).
- Access to the container registries and repositories in scope.
- Defined severity thresholds and a waiver process for accepted risks.
- SBOM or image inventory so scan coverage can be measured (scanning 60% of images is a finding about the program, not the images).
- Owners for triage: someone must disposition every failing result.

## Procedure

1. **Set up and update the vulnerability database.** Install Trivy, run `trivy image --download-db-only` (or configure the DB repository mirror), and schedule regular DB updates. Stale databases produce false confidence; verify the DB timestamp in scan output.
2. **Scan images in CI at build time.** Add `trivy image --severity HIGH,CRITICAL --exit-code 1` (tuned to your threshold) as a pipeline gate on every image build. Scan the final image, not intermediate stages, and fail the build on threshold violations unless a valid waiver exists.
3. **Scan the existing registry estate.** Run Trivy across all images in your registries to establish the backlog: `trivy image` per repository tag, aggregated into a report. Prioritize by deploy status — a critical CVE in an image actually running in production outranks one in a stale dev tag.
4. **Add misconfiguration and secret scanning.** Enable Trivy's config scanning for Dockerfiles, Kubernetes manifests, and Terraform (`trivy config`), and its secret scanner on repositories. Many "vulnerabilities" that matter are misconfigurations Trivy finds without any CVE database.
5. **Triage with context.** For each finding, determine: is the vulnerable package actually reachable at runtime (distroless/minimal images often include unreachable packages), is there a fixed version available, and does your base image maintainer already ship a patch? Suppress only with time-boxed waivers that name the owner and expiry.
6. **Correlate with runtime.** Join scan results with what is actually deployed: an image with 40 highs sitting in the registry is hygiene; the same image running as a privileged pod is an incident waiting to happen. Feed Trivy results into your asset inventory for this join.
7. **Track remediation metrics.** Measure: mean time to remediate critical image CVEs, percentage of builds passing the gate, waiver aging, and DB freshness. Report trends, not just counts — leadership needs to see whether the backlog is shrinking.
8. **Maintain the practice.** Review thresholds quarterly, audit waivers for expiry, keep Trivy and its DB current, and extend scanning to new artifact types (e.g., VM images, language-specific lockfiles) as the estate evolves.

## Expected outputs

- Trivy integrated as a CI gate with defined severity thresholds and waiver handling.
- A registry-wide scan baseline with prioritized remediation backlog.
- Misconfiguration and secret-scan findings for IaC and Dockerfiles.
- Triage records distinguishing reachable vs. unreachable findings, with time-boxed waivers.
- Program metrics: gate pass rate, remediation time, waiver aging, DB freshness.

## Pitfalls

- Failing builds on every low-severity finding — developers will route around the gate; threshold at high/critical and handle the rest as backlog.
- Scanning images but never the running estate; the registry is not the risk, the deployment is.
- Permanent suppressions instead of time-boxed waivers — accepted risk must be re-accepted.
- Outdated vulnerability databases silently passing vulnerable images; monitor DB age as a control.
- Treating scanner output as the remediation plan; someone still has to update the base image or dependency and rebuild.

## References

- Trivy documentation (Aqua Security)
- NIST SP 800-190, "Application Container Security Guide"
- CIS Docker Benchmark
- NVD (National Vulnerability Database) for CVE verification
- CISA KEV catalog for prioritizing exploited vulnerabilities found in scans
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
