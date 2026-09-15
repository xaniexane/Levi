---
skill_id: cyber_building_devsecops_pipeline_with_gitlab_ci
name: Building a DevSecOps Pipeline with GitLab CI
description: Practitioner guide to embedding security gates -- SAST, SCA, secrets detection, container scanning, and DAST -- into GitLab CI pipelines.
risk: info
permissions: []
requires_confirmation: false
tags: [devsecops, appsec, automation]
version: 1.0.0
---
## Purpose
This playbook shows how to build a GitLab CI pipeline where security checks run as first-class stages rather than afterthoughts: static analysis, dependency scanning, secrets detection, container and infrastructure-as-code scanning, and dynamic testing, each with clear failure policies. The goal is fast feedback for developers with minimal pipeline friction.

## When to use
- Introducing security automation into an existing GitLab CI workflow.
- Reducing the time between code commit and vulnerability discovery.
- Standardizing security gates across many repositories.
- Preparing for audit evidence that security testing is continuous and enforced.

## Prerequisites
- GitLab project with CI/CD enabled and runner capacity for scanning jobs.
- Selected scanning tools (GitLab built-in analyzers or third-party equivalents).
- Policy decisions: which findings break the build versus warn, per severity and branch.
- Developer communication channel for rolling out new gates.

## Procedure
1. Map the pipeline stages. Define stages such as validate, test, scan, build, deploy, and decide where each security check runs; fast checks run early.
2. Enable secrets detection. Add the secrets analyzer to every pipeline so committed credentials are caught before merge; configure it to scan history on the default branch.
3. Add SAST. Integrate static application security testing on merge requests, tuned to the repository languages; establish a baseline and triage legacy findings separately.
4. Add SCA. Scan dependencies and lockfiles for known vulnerabilities; set policy on direct versus transitive dependencies.
5. Scan containers and IaC. If the project builds images, add container scanning; scan Terraform or Kubernetes manifests for misconfigurations.
6. Add DAST for deployable apps. Run dynamic scans against a staging environment on schedule or per release, not on every commit.
7. Define failure policies. Block merges on new critical and high findings; allow warnings with tracked exceptions for legacy issues with expiry dates.
8. Measure and iterate. Track mean time to fix, scan duration, and developer override rates; tune rules quarterly and report trends to engineering leadership.

## Expected outputs
- GitLab CI pipeline with security stages and documented failure policies.
- Baseline vulnerability report with triaged exceptions and owners.
- Metrics dashboard: scan coverage, time to fix, and gate override rate.

## Pitfalls
- Blocking builds on noisy, untrusted findings destroys developer buy-in; tune first, enforce second.
- Scans that double pipeline time get disabled; parallelize and cache aggressively.
- Ignoring transitive dependencies misses the bulk of real-world supply-chain risk.
- Secrets committed before the gate existed need a history sweep, not just forward scanning.

## References
- GitLab documentation: application security and CI/CD pipeline configuration
- OWASP DevSecOps Guideline
- NIST SP 800-218, Secure Software Development Framework (SSDF)
- CIS Benchmarks for container and pipeline hardening
