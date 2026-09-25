---
skill_id: cyber_implementing_secret_scanning_with_gitleaks
name: Implementing Secret Scanning with Gitleaks
description: Detect leaked secrets in git repositories with Gitleaks — pre-commit hooks, CI scanning, full-history audits, and coordinated revocation workflows.
risk: info
permissions: []
requires_confirmation: false
tags: [secrets, scanning, devsecops, gitleaks]
version: 1.0.0
---
## Purpose

Find the API keys, tokens, passwords, and private keys developers inevitably commit — and stop new ones at the door. Gitleaks scans git repositories (working tree, staged changes, and full history) with an extensive rule set for secret patterns. Deployed as pre-commit hooks, CI checks, and periodic history audits, it converts secret leakage from "discovered during incident response" to "blocked at commit time."

## When to use

- Preventing secret leakage in source code (the most common initial finding in every code audit).
- Auditing repository history for secrets committed before scanning existed.
- Meeting secret-management expectations (SOC 2, PCI DSS 4.0, internal policy).
- Responding to a leaked-secret incident: finding everywhere the secret appears.
- Complementing (not replacing) proper secrets management — scanning catches failures of the primary control.

## Prerequisites

- Repository inventory across the organization (including forks, mirrors, and archived repos — secrets don't respect archive status).
- Gitleaks installed and configured (version pinned; custom rules file for organization-specific secret formats).
- Defined secret-handling policy: what developers should use instead (vault, env injection, secret managers).
- Revocation authority: who can revoke which secret types quickly (cloud IAM, API providers) when leaks are found.
- Baseline scan results so the first enforced run doesn't block every pipeline simultaneously.

## Procedure

1. **Configure Gitleaks with organization rules.** Start from the default rule set and add custom rules for internal secret formats (internal API key prefixes, proprietary token patterns). Maintain an allowlist for test fixtures and documented false positives — but require each allowlist entry to carry justification and expiry. Pin the Gitleaks version in all deployments.
2. **Scan full history first (privately).** Run `gitleaks detect --source . --verbose` across all repositories including history, before announcing enforcement. Triage the findings: live secrets get revoked immediately (assume compromise — a secret in git history is a secret the internet may have), dead test keys get documented, false positives feed the allowlist. This initial sweep is often alarming; handle it as an incident-response-lite exercise.
3. **Deploy pre-commit hooks.** Install Gitleaks as a pre-commit hook (via pre-commit framework) so secrets are blocked before the commit is even created:
   ```yaml
   - repo: https://github.com/gitleaks/gitleaks
     rev: v8.x.x
     hooks:
       - id: gitleaks
   ```
   Pre-commit is the friendliest enforcement point — the developer fixes it in seconds with no pipeline involvement.
4. **Enforce in CI on pull requests.** Add Gitleaks to CI scanning the PR diff (fast) and, on a schedule, the full repository (thorough). Fail the build on new findings; report-only on historical findings already triaged. Developers bypass pre-commit hooks routinely (`--no-verify`); CI is the backstop that can't be skipped.
5. **Scan continuously, not just at commit.** Schedule full-history scans (weekly) to catch secrets introduced via rebases, force-pushes, and hook bypasses. Monitor the major code-hosting platforms' own secret-scanning alerts (GitHub secret scanning, GitLab) as a complementary signal — defense in depth for the thing developers are best at leaking.
6. **Build the revocation runbook.** Every confirmed live secret triggers: immediate revocation/rotation at the provider, audit of the secret's usage logs for unauthorized access (assume the worst — check), removal from git history where feasible (BFG/ filter-repo, understanding that history rewrite doesn't un-leak), and a blameless post-mortem on how it got committed. Speed matters more than elegance here.
7. **Drive developers to secret managers.** Scanning without an alternative is just nagging. Provide the paved path: vault/secret-manager integration patterns per stack, local development workflows (env files gitignored, dev secret provisioning), and CI secret injection. Track the metric that matters: secrets-committed per month trending to zero.
8. **Govern and tune.** Monthly review of findings: new secret types needing custom rules, allowlist expiries, bypass patterns (base64-encoded secrets, split secrets — tune rules for the evasion techniques your developers actually use). Report secret-leak metrics to engineering leadership.

## Expected outputs

- Gitleaks configured with default + custom rules, version-pinned everywhere.
- Full-history audit completed with live secrets revoked.
- Pre-commit hooks deployed; CI enforcement on PRs; scheduled full scans.
- Secret revocation runbook with usage-audit procedures.
- Developer guidance for secret managers; leak metrics trending down.

## Pitfalls

- **Scanning only the working tree.** Secrets live in history, in stashes, in other branches. Scan everything or accept the blind spots explicitly.
- **Blocking without an alternative.** Telling developers "don't commit secrets" without providing the vault workflow just produces more creative hiding. Paved path first, enforcement second.
- **Treating revoked-in-history as safe.** Once pushed to a shared remote (especially public), a secret is compromised — period. History rewriting is hygiene, not remediation. Rotate first, clean second.
- **Allowlist sprawl.** Overly broad allowlists (entire files, whole directories) become the standard bypass. Keep allowlists narrow, justified, and expiring.
- **Forgetting non-code locations.** Secrets leak into wikis, tickets, chat logs, CI logs, and container layers too. Gitleaks covers repos; extend the program's thinking to the other surfaces.

## References

- Gitleaks documentation — https://github.com/gitleaks/gitleaks
- NIST SP 800-57 (key management — why committed secrets must be rotated) — https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final
- MITRE ATT&CK T1552 (Unsecured Credentials) — https://attack.mitre.org/techniques/T1552/
- GitHub secret scanning documentation — https://docs.github.com/en/code-security/secret-scanning
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
