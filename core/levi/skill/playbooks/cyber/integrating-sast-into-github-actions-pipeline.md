---
skill_id: cyber_integrating_sast_into_github_actions_pipeline
name: Integrating SAST into the GitHub Actions Pipeline
description: Embed static analysis scanning into GitHub Actions with actionable developer feedback.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, sast, devsecops]
version: 1.0.0
---
## Purpose
This playbook embeds SAST into GitHub Actions so every pull request gets static analysis feedback where developers already work: fast scans on PRs, deeper scans on schedule, and SARIF results surfaced in code scanning alerts.

## When to use
- Code merges without any static security analysis.
- Security findings arrive weeks after the code shipped, when fixes are expensive.
- Standardizing AppSec across repositories in a GitHub organization.

## Prerequisites
- Chosen SAST engine(s): CodeQL, Semgrep, or a commercial scanner with a GitHub Action.
- Organization-level ability to enforce required workflows or reusable workflows.
- Agreed severity policy: what blocks a merge vs. what becomes backlog.

## Procedure
1. **Pick the engine per language.** Use CodeQL for deep analysis of supported languages and Semgrep for fast, customizable rules; they complement rather than replace each other.
2. **Create a reusable workflow.** Build one organization-wide workflow (scan job, SARIF upload) that repositories call, so policy changes propagate without editing every repo.
3. **Scan pull requests differentially.** Run fast scans on PRs and surface new findings as PR annotations and code scanning alerts; developers fix their own code before merge.
4. **Run deep scans on schedule.** Weekly full CodeQL scans catch what the fast pass misses; triage results in the security dashboard, not in the PR.
5. **Upload SARIF to code scanning.** Standardize on SARIF output so results appear in GitHub's code scanning UI with consistent severity and CWE mapping.
6. **Tune and suppress deliberately.** Write custom Semgrep/CodeQL rules for org-specific patterns; suppressions must be in-code with justification, time-boxed, and reviewed.
7. **Enforce with branch protection.** Require the security check on protected branches for high-risk repos after false-positive rates are acceptable; measure fix rates.

8. **Cover infrastructure-as-code.** Extend the workflow to scan Terraform, Dockerfiles, and CI configs; misconfigured infrastructure is a vulnerability too.
9. **Report to developers in their language.** Frame findings as code locations with fix examples, not CVE dumps; adoption follows usability.

## Expected outputs
- Reusable SAST workflow adopted across repositories with SARIF reporting.
- PR-time feedback loop and scheduled deep scans.
- Metrics: new findings per PR, mean time to fix, suppression inventory.
- Example: a PR introducing unsanitized SQL concatenation gets a CodeQL annotation with the exact sink location and a parameterized-query fix suggestion before merge.

## Pitfalls
- Blocking merges on day one with untuned rules: developers route around the check.
- Treating SAST as the whole AppSec program; it misses runtime, dependency, and design flaws.
- Suppressions without expiry that silently accumulate into blind spots.

- Scanning only the default branch while feature branches merge untested code; PR-time scans are the control that matters.
- Letting the security workflow become the slowest job in the pipeline; developers will demand its removal if it blocks every merge for 40 minutes.

## References
- GitHub code scanning documentation (docs.github.com/code-security/code-scanning).
- OWASP Code Review Guide (owasp.org/www-project-code-review-guide).
- Semgrep documentation (semgrep.dev/docs) — custom rule authoring.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
