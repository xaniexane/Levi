---
skill_id: cyber_implementing_github_advanced_security_for_code_scanning
name: Code Scanning with GitHub Advanced Security
description: Enable GitHub Advanced Security code scanning: CodeQL, secret scanning, and dependency review in the PR flow.
risk: low
permissions: []
requires_confirmation: false
tags: [devsecops, scanning]
version: 1.0.0
---
## Purpose
GitHub Advanced Security (GHAS) puts SAST, secret scanning, and supply-chain checks where developers
already work: the pull request. CodeQL finds real vulnerabilities (not just patterns), secret
scanning catches leaked credentials, and dependency review blocks risky PRs. This playbook enables
GHAS across the organization with tuned configurations, fair policies, and metrics — the
GitHub-native DevSecOps scanning layer.

## When to use
- Standardizing code scanning across GitHub-hosted repositories.
- After incidents involving leaked secrets, vulnerable dependencies, or missed code flaws.
- Meeting secure-SDLC requirements with GitHub-native tooling (SOC 2, PCI DSS 6.x, SSDF).
- Before scaling the engineering org: scanning must precede repo sprawl.
- As the code-scanning component of the broader DevSecOps pipeline.

## Prerequisites
- GHAS licensing for the organization (or eligible public repos).
- Defined severity policy: what blocks merges vs. warns, per scanning type.
- Repository inventory: which repos are in scope, their languages, and criticality.
- Code-owner and security-team routing: who triages findings per repo.
- Baseline expectation: legacy repos will have findings — plan the backlog approach.

## Procedure
1. **Enable secret scanning first (organization-wide).** Turn on secret scanning and push protection
   for all repos. Push protection blocks secret commits at push time — the highest-ROI GHAS feature.
   Also run a historical scan: existing leaked secrets get rotated, not just noted. Document the
   rotation runbook.
2. **Enable Dependabot and dependency review.** Turn on Dependabot alerts and security updates
   (auto-PRs for patchable vulns), plus dependency review on PRs to block new vulnerable
   dependencies. Configure: auto-merge for patch-level security updates where tests pass; human
   review for major bumps.
3. **Roll out CodeQL code scanning.** Enable default CodeQL setup (or advanced for custom queries)
   per language. Start with the `security-extended` or default queries on PRs; schedule full scans
   on main branches. Default setup is genuinely good — customize only after measuring.
4. **Tune for precision.** Review initial findings: suppress false positives with documented
   justification (in-code suppressions with reason, not blanket ignores), write custom CodeQL
   queries for org-specific dangerous patterns (banned crypto, internal risky APIs), and tune
   severity to match your policy.
5. **Design fair merge policies.** Block merges on: new high/critical CodeQL findings, new critical
   dependency CVEs, and any pushed secrets. Don't block on pre-existing findings — backlog those
   with SLAs. Use rulesets to enforce consistently; exemptions need security approval with expiry.
6. **Route findings to owners.** Code scanning alerts auto-assign to PR authors and code owners;
   create tracking issues for main-branch findings with SLAs. The security team monitors the backlog
   and helps with hard findings — they don't own every alert.
7. **Handle the legacy backlog.** Triage existing findings: fix the critical/highs on a schedule,
   document risk-accepted items with expiry, and track burn-down. Show progress — a shrinking
   backlog proves the program works and justifies continued investment.
8. **Extend with custom workflows.** Add: license compliance checks (dependency review
   customization), IaC scanning via third-party actions where GHAS doesn't cover, and
   secret-scanning custom patterns for internal token formats (API keys, employee IDs). GHAS is the
   platform; extend it to your specifics.
9. **Monitor GHAS health.** Alert on: failed CodeQL runs (broken builds silently lose coverage),
   disabled scanning on repos (policy drift), and Dependabot PR pileups (unmerged security updates
   are unapplied fixes). Coverage percent (repos with scanning enabled and green) is the headline
   metric.
10. **Report and mature.** Metrics: new findings introduced per PR, mean time to fix by severity,
    secret-push blocks, Dependabot update lag, and coverage. Quarterly: review query packs, custom
    patterns, policy strictness, and whether findings correlate with fewer production
    vulnerabilities (the ultimate validation).

## Expected outputs
- Secret scanning + push protection org-wide with historical leak rotation completed.
- Dependabot alerts/updates and dependency review gating PRs.
- CodeQL on PRs and main branches with tuned queries and custom org patterns.
- Fair merge policies via rulesets (block new criticals; backlog legacy) with exemption control.
- Health monitoring, coverage metrics, and quarterly maturity reviews.

## Pitfalls
- Blocking on legacy findings: every PR fails, developers demand the gate removed. Gate on new
  findings; backlog the rest.
- Push protection without a rotation runbook: blocked developers need to know how to clean and
  rotate, not just that they're blocked.
- Ignoring failed scans: a red CodeQL run that nobody fixes is silent loss of coverage. Monitor scan
  health like production.
- Dependabot PR neglect: auto-opened security updates that sit unmerged for months are theater.
  Track update lag and auto-merge patches where safe.
- One-size-fits-all queries: org-specific risks (internal frameworks, custom crypto) need custom
  queries — default packs don't know your stack.

## References
- GitHub Advanced Security documentation (code scanning, secret scanning, dependency review)
- CodeQL documentation (query writing, default suites)
- NIST SP 800-218 (SSDF — tooling mappings)
- OWASP SAMM (maturity model for the scanning program)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
