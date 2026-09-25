---
skill_id: cyber_integrating_dast_with_owasp_zap_in_pipeline
name: Integrating DAST with OWASP ZAP in the Pipeline
description: Run OWASP ZAP dynamic scans in CI/CD to catch runtime web vulnerabilities early.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, dast, devsecops]
version: 1.0.0
---
## Purpose
This playbook integrates OWASP ZAP dynamic application security testing into CI/CD: baseline scans on every build, fuller scans on schedule, and failure policies that block releases on high-severity findings without grinding development to a halt.

## When to use
- Web applications ship without any runtime security testing.
- SAST exists but misses runtime issues (auth flaws, session handling, server misconfigurations).
- You need a free, automatable DAST tool that runs in containers.

## Prerequisites
- A deployable test instance of the application per pipeline run (staging or ephemeral environment).
- Seeded test data and test credentials so the scanner can exercise authenticated areas.
- Agreement on the break-the-build policy: which severities fail the pipeline.

## Procedure
1. **Start with the baseline scan.** Add the ZAP baseline scan (spider + passive checks) to the pipeline; it is fast and safe enough for every commit or nightly build.
2. **Provide authenticated context.** Configure ZAP authentication (form-based, script, or token) so scans cover logged-in functionality, where most real flaws live.
3. **Tune the scope.** Define include/exclude contexts: scan your application, not third-party widgets; exclude destructive endpoints (data deletion, mass email) from active scanning.
4. **Add scheduled full scans.** Run the full active scan weekly against staging with carefully scoped attack strength; review results before they gate anything.
5. **Gate releases on severity.** Fail the pipeline on high findings after tuning; report mediums as warnings assigned to the backlog with SLAs.
6. **Manage false positives as code.** Maintain an ignore/alert-filter configuration in the repo with justification and expiry, reviewed by security.
7. **Track trends.** Record finding counts and classes per build; use the trend to measure whether the codebase is getting safer.

8. **Scan authenticated areas.** Invest in robust login handling for ZAP; unauthenticated scans miss the majority of real application flaws.
9. **Combine with SAST findings.** Correlate DAST results with SAST output for the same build to prioritize issues confirmed by both methods.

## Expected outputs
- Pipeline-integrated ZAP baseline scans with authenticated contexts.
- Break-the-build policy and false-positive filter under version control.
- Trend metrics on DAST findings per release.
- Example: a nightly baseline scan flags a missing security header on a new endpoint; the finding is auto-filed to the owning team with the exact request that triggered it.

## Pitfalls
- Active-scanning production: rate limits, data corruption, and angry users.
- Unauthenticated scans that only test the login page and declare victory.
- Failing builds on untuned results, which teaches developers to disable the scan.

- Running the baseline scan against a seeded database that does not resemble production data shapes; findings do not transfer to real data flows.
- Ignoring ZAP's passive-scan findings because "they are only informational"; passive findings often reveal the most useful attack surface.

## References
- OWASP ZAP documentation (zaproxy.org/docs).
- OWASP Testing Guide (owasp.org/www-project-web-security-testing-guide).
- OWASP Top 10 (owasp.org/Top10) — risk framing for DAST findings.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
