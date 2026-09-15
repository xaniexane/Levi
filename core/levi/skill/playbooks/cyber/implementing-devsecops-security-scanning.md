---
skill_id: cyber_implementing_devsecops_security_scanning
name: DevSecOps Security Scanning in CI/CD
description: Embed SAST, SCA, secrets, IaC, and container scanning into CI/CD with developer-friendly gates.
risk: low
permissions: []
requires_confirmation: false
tags: [devsecops, scanning]
version: 1.0.0
---
## Purpose
Vulnerabilities are cheapest to fix where they're introduced: in the pull request, minutes after the
code is written — not in production months later. DevSecOps scanning embeds security checks into
CI/CD (SAST, software composition analysis, secrets detection, IaC scanning, container scanning)
with fast feedback and fair gates. This playbook implements the scanning toolchain as a
developer-enabling program, not a compliance tollbooth.

## When to use
- Shifting security left in organizations with active CI/CD but ad-hoc or absent pipeline scanning.
- After incidents rooted in known-vulnerable dependencies, hardcoded secrets, or misconfigured IaC.
- Meeting secure-SDLC requirements (SOC 2, PCI DSS 6.x, SLSA, EO 14028).
- Before scaling engineering: scanning must be in place before the codebase doubles.
- As the preventive layer beneath pentesting and bug bounty (fewer trivial findings for humans to
  find).

## Prerequisites
- CI/CD platform access to add pipeline stages (GitHub Actions, GitLab CI, Jenkins, etc.).
- Defined severity policy: what blocks merges vs. warns, per scanner type.
- Developer buy-in: scanning that developers hate gets bypassed. Involve them in tool and threshold
  choices.
- Baseline of existing findings: legacy code will have issues — plan the backlog, not just the gate.
- Ticketing integration for findings that don't block but must be tracked.

## Procedure
1. **Start with secrets detection.** It's the fastest win and the least controversial: scan every
   commit for keys, tokens, and credentials (gitleaks, trufflehog, or platform-native). Block merges
   on new secrets; provide the rotation runbook for when one slips through. Also scan history once
   for existing leaked secrets and rotate them.
2. **Add software composition analysis (SCA).** Scan dependencies for known CVEs on every build
   (Dependabot/Renovate + advisories, Snyk, OWASP Dependency-Check). Gate on: critical CVEs with
   fixes in direct dependencies. Auto-open PRs for patch updates — make the fix as easy as the
   finding.
3. **Add SAST with tuned rules.** Deploy static analysis (Semgrep, CodeQL, SonarQube) on pull
   requests. Start with high-precision rulesets (injection, auth flaws, crypto misuse); tune out
   noisy rules quickly. Developers should see findings as code comments in the PR, not in a separate
   portal they never open.
4. **Scan infrastructure as code.** Add Checkov/tfsec/KICS to IaC pipelines: fail on critical
   misconfigurations (public storage, open security groups, unencrypted data stores). IaC scanning
   is the cheapest CSPM — fix the template, fix every deployment.
5. **Scan containers at build.** Image scanning on every build (see the Aqua playbook): block
   promotion on critical fixable CVEs and misconfigurations (root user, secrets in layers). Keep
   scan times acceptable — slow pipelines get skipped.
6. **Design fair gates.** Block on: new critical/high findings introduced by the change (not
   pre-existing debt — that's the backlog). Warn on mediums. Never block on informational.
   Grandfather existing findings with a tracked remediation backlog and a burn-down target, so the
   gate is fair from day one.
7. **Make findings actionable in the developer workflow.** Every finding needs: file/line, why it
   matters (one sentence), and how to fix (with example). Findings appear in the PR; the security
   portal is for trends, not triage. Measure and minimize false-positive rates per rule — noisy
   rules get disabled fast.
8. **Track the backlog honestly.** Non-blocking findings ticket to teams with SLAs. Report: new
   findings introduced per sprint, backlog burn-down, mean time to fix by severity, and scanner
   coverage (repos/pipelines with scanning enabled). Coverage percent is the program's headline
   metric.
9. **Secure the pipeline itself.** Scanning is moot if the pipeline is compromised: protect CI
   runners (ephemeral, least-privilege), pin third-party actions by SHA, require code-owner review
   for pipeline changes, and use OIDC federation instead of long-lived cloud credentials.
   Supply-chain attacks target the pipeline.
10. **Evolve continuously.** Quarterly: review scanner effectiveness (are findings that matter being
    caught? are pentests still finding trivial issues?), adopt new scanners for new tech (IaC for
    new platforms, API scanning), and tighten gates as the backlog shrinks. The program matures with
    the codebase.

## Expected outputs
- Pipeline scanning: secrets, SCA, SAST, IaC, and container scans on every PR/build.
- Fair gating policy (block on new critical/high; backlog for legacy) with developer buy-in.
- Findings delivered in-PR with fix guidance; backlog tracked with SLAs.
- Coverage metrics and burn-down reporting.
- Hardened pipeline (pinned actions, OIDC, ephemeral runners, reviewed pipeline changes).

## Pitfalls
- Blocking on legacy debt: failing every build for pre-existing findings guarantees the gate gets
  disabled. Gate on new findings; backlog the rest.
- Scanner sprawl without tuning: five noisy scanners produce alert fatigue and universal ignore.
  Fewer, well-tuned scanners beat more noisy ones.
- Findings outside the developer workflow: a separate portal nobody opens is where findings go to
  die. In-PR or it didn't happen.
- Slow pipelines: 30-minute security stages get bypassed. Optimize scan speed (incremental, cached)
  — performance is a security feature.
- Unsecured pipeline: attackers who own CI own everything it deploys. Harden the pipeline with the
  same rigor as production.

## References
- OWASP DevSecOps Guideline and SAMM (maturity model for secure SDLC)
- NIST SP 800-218 (Secure Software Development Framework, SSDF)
- SLSA framework (build integrity levels)
- CIS Software Supply Chain Security Guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
