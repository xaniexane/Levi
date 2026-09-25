---
skill_id: cyber_implementing_infrastructure_as_code_security_scanning
name: Implementing Infrastructure as Code Security Scanning
description: Shift cloud misconfiguration detection left by scanning Terraform, CloudFormation, and Kubernetes manifests in CI with policy-as-code scanners.
risk: info
permissions: []
requires_confirmation: false
tags: [iac, cloud, devsecops, scanning]
version: 1.0.0
---
## Purpose

Catch insecure infrastructure before it is deployed: unencrypted storage, public buckets, open security groups, missing logging, and privileged defaults — expressed as code and therefore testable as code. This playbook stands up IaC scanning (Checkov, tfsec, KICS, Conftest) in the pipeline so misconfigurations fail the build instead of becoming findings in production.

## When to use

- Adopting Terraform, CloudFormation, Pulumi, or Kubernetes manifests at any scale.
- Reducing recurring CSPM findings that trace back to code, not console drift.
- Meeting compliance expectations (CIS Benchmarks, PCI DSS 4.0, SOC 2) for infrastructure baselines.
- Standardizing guardrails across teams without becoming the team that hand-reviews every pull request.
- Post-incident, when a breach traces to a misconfigured resource that was deployed as code.

## Prerequisites

- IaC repositories under version control with a defined CI pipeline (GitHub Actions, GitLab CI, Jenkins, etc.).
- Agreement on the baseline: which CIS Benchmark level or internal hardening standard the scans enforce.
- Scanner selection per IaC type: Checkov or tfsec for Terraform, cfn-nag/cfn-lint for CloudFormation, kube-linter/kubeconform for manifests, plus Conftest/OPA for custom policy.
- A process for suppressions: who can approve them, how they expire, and where they are logged.
- Baseline scan results for existing code so the first enforced run does not block every team simultaneously.

## Procedure

1. **Pick the scanner set and pin versions.** Standardize on one primary scanner per IaC dialect (e.g., Checkov for Terraform/CloudFormation/K8s, tfsec as a fast complement) and pin versions in CI — scanner rule updates change results, and unpinned scanners produce non-reproducible pipelines.
2. **Define the policy baseline.** Start from CIS Benchmark mappings the scanners ship with, then layer organization-specific rules (naming, tagging, allowed regions, approved AMIs) as custom OPA/Rego policies via Conftest. Keep custom rules in their own repo with tests.
3. **Scan on pull request, fail thoughtfully.** Add the scan as a required check on PRs touching IaC paths. Fail the build on HIGH/CRITICAL findings; report MEDIUM/LOW as annotations. Grandfather existing violations with a time-boxed waiver list rather than blocking all delivery on day one.
4. **Scan the plan, not just the code.** Run scanners against `terraform plan` output (JSON) in addition to static files so computed values, data-source lookups, and module expansions are evaluated as they will actually deploy.
5. **Gate the deployment pipeline.** Re-run the scan at the deploy stage against the exact artifact being applied — PR-time code and deploy-time code can differ. Block `terraform apply` on new HIGH/CRITICAL findings.
6. **Manage suppressions like exceptions.** Require inline suppressions to carry a justification and ticket reference, expire them (e.g., 90 days), and report on suppression inventory monthly. A suppression without an owner is a permanent hole.
7. **Close the loop with runtime.** Feed scanner rule IDs into CSPM/drift detection so a finding in production maps back to the line of code and the PR that introduced it. Track mean-time-to-fix per rule to find the policies developers fight — usually a sign the rule or the pattern needs work.
8. **Tune continuously.** Review false positives weekly at first, then monthly. Disable or rewrite noisy rules rather than training developers to ignore scanner output.

## Expected outputs

- CI pipeline stages scanning IaC on PR and at deploy time, with pinned scanner versions.
- Documented policy baseline (CIS level + custom rules) with owner sign-off.
- Waiver/suppression register with expiries and ticket links.
- Metrics: findings by severity over time, MTTR per rule, suppression inventory.
- Runbook mapping production CSPM findings back to source code.

## Pitfalls

- **Scanning only static files.** Modules, remote state, and computed values change what actually deploys; plan-output scanning catches what static scanning misses.
- **Failing everything on day one.** Turning on blocking mode against a legacy codebase halts delivery and gets the control disabled. Baseline, waive with expiry, then enforce incrementally.
- **Unpinned scanners.** A scanner auto-update that adds rules will red-build every pipeline on a Monday morning. Pin and upgrade deliberately.
- **Suppression sprawl.** Inline `#checkov:skip` comments multiply silently; audit them or they become the standard way to ship misconfigurations.
- **No drift coverage.** IaC scanning proves the code is clean, not the cloud. Pair with drift detection — console changes bypass the pipeline entirely.

## References

- Checkov documentation — https://www.checkov.io/
- CIS Benchmarks (Terraform, Kubernetes, cloud provider baselines) — https://www.cisecurity.org/cis-benchmarks
- NIST SP 800-204 (container/IaC-adjacent security practices) — https://csrc.nist.gov/
- MITRE ATT&CK T1578 (Modify Cloud Compute Infrastructure) — https://attack.mitre.org/techniques/T1578/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
