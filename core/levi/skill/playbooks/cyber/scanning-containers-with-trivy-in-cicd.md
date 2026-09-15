---
skill_id: cyber_scanning_containers_with_trivy_in_cicd
name: Scanning Containers with Trivy in CI/CD
description: Integrate Trivy image and filesystem scanning into CI/CD pipelines with severity gates and SARIF reporting.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, cicd, trivy]
version: 1.0.0
---
## Purpose
Shifting container scanning left catches vulnerabilities before images reach the registry. This playbook covers integrating Aqua's Trivy into CI/CD: scanning the built image and repository, failing builds on policy violations, publishing SARIF to code-scanning dashboards, and keeping the gate fast enough that developers do not bypass it.

## When to use
- Building a secure software supply chain for containerized services.
- Adding guardrails to an existing pipeline that currently ships unscanned images.
- Compliance requirements for vulnerability scanning of built artifacts.
- After an incident traced to a vulnerable dependency in a shipped image.

## Prerequisites
- CI/CD platform with permission to run containers or the Trivy binary.
- Trivy vulnerability database cached or mirrored for pipeline speed and reliability.
- Defined policy: which severities fail the build vs warn.
- Code-scanning integration (e.g. GitHub code scanning, GitLab) for SARIF upload.

## Procedure
1. Add a pipeline stage after image build that runs Trivy against the local image tag.
2. Scan both the OS packages and language dependencies (`--scanners vuln`).
3. Set exit-code behavior: fail on critical/high with fixes available; warn-only for unfixed or low initially.
4. Upload SARIF output to the platform's code-scanning dashboard for developer visibility.
5. Cache the Trivy DB between runs to keep pipeline time acceptable; refresh on a schedule.
6. Maintain an allowlist file for accepted-risk CVEs with owner and expiry; review it regularly.
7. Extend scanning to the repository filesystem and IaC for misconfigurations in the same stage.
8. Monitor gate metrics: scan duration, failure rate, and time-to-fix for failed builds.
9. Scan the image by digest, not tag, so the gate evaluates exactly what will ship.
10. Refresh both the vulnerability DB and the Java DB on schedule; they update independently.
11. Add a scheduled pipeline run for base images even when application code has not changed.

## Expected outputs
- Pipeline definition with Trivy stage, policy, and SARIF upload.
- Accepted-risk allowlist with owners and expiry dates.
- Metrics: scan coverage, gate failures, and remediation times.
- Digest-pinned gate evaluation records.
- Database refresh schedule and compliance log.
- Base-image-only scan results for dormant repositories.

## Pitfalls
- Failing builds on every CVE on day one blocks all delivery; phase the gate in starting with criticals.
- Stale DB caches produce stale results; automate refresh.
- Allowlist without expiry becomes permanent exception debt.
- Scanning only the final image misses build-time secrets; add secret scanning too.
- Trivy's Java DB and vulnerability DB update independently; refreshing one is not enough.
- Pipelines that only scan on code changes miss base-image CVEs; schedule periodic scans.
- Ignoring the DB download failure silently gates on stale data; alert on refresh failures.
- Pipeline scan results that developers cannot see are ignored; surface them in the PR, not just logs.

## References
- Aqua Trivy documentation (aquasecurity.github.io/trivy).
- NIST SP 800-204, Security Strategies for Microservices-based Applications.
- SLSA framework (slsa.dev) for supply-chain levels.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
