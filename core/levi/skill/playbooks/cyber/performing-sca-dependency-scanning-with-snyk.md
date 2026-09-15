---
skill_id: cyber_performing_sca_dependency_scanning_with_snyk
name: SCA Dependency Scanning with Snyk
description: Scan software dependencies with Snyk for known vulnerabilities and license risks, and integrate fixes into development workflows.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, sca, snyk]
version: 1.0.0
---

## Purpose
- Find known-vulnerable open-source dependencies before attackers exploit them in production.
- Prioritize dependency findings by reachability and exploitability, not just CVSS scores.
- Embed scanning into developer workflows so fixes happen early and cheaply.

## When to use
- Continuously in CI/CD pipelines for every build.
- When onboarding new projects or acquiring code through M&A.
- After major vulnerability disclosures affecting common libraries.
- During audits that require evidence of software composition analysis.

## Prerequisites
- Snyk account and CLI or CI integration with access to the code repositories.
- An inventory of projects, package managers, and languages in scope.
- A vulnerability management process with SLAs for fixing dependency issues.
- Developer buy-in: scanning must help developers, not just generate tickets.

## Procedure
1. Connect repositories to Snyk and run baseline scans across all in-scope projects.
2. Review the baseline for critical issues, prioritizing reachable and directly-exploited vulnerabilities.
3. Configure policies: fail builds on new critical issues, warn on high, and track everything else.
4. Integrate Snyk into pull requests so developers see fix advice at code-review time.
5. Use fix pull requests or upgrade guidance, testing changes in CI before merging.
6. Address transitive dependencies by upgrading the direct dependency that pulls them in.
7. Handle license findings: flag copyleft or unapproved licenses for legal review.
8. Monitor continuously; new vulnerabilities are disclosed daily against already-shipped code.
9. Track metrics: mean time to fix, percentage of projects scanned, and critical-issue aging.
10. Review and tune policies quarterly so they stay aligned with risk appetite and developer velocity.

## Expected outputs
- A dependency vulnerability inventory with prioritized remediation.
- CI/CD-integrated scanning with policy gates.
- Metrics showing fix velocity and coverage trends.
- A software bill of materials (SBOM) generated for each release.
- An exception process for vulnerabilities with no available fix, with compensating controls.

## Pitfalls
- Drowning developers in low-severity findings; prioritize ruthlessly or scanning gets ignored.
- Auto-merging dependency upgrades without tests; broken builds erode trust in the program.
- Scanning only direct dependencies while transitive ones carry the actual risk.
- Ignoring container base images, which carry their own dependency vulnerabilities.

## References
- NTIA minimum elements for SBOM guidance
- Snyk official documentation
- OWASP guidance on vulnerable and outdated components
- NIST SP 800-161 on supply chain risk management
- CISA guidance on software bill of materials (SBOM)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
