---
skill_id: cyber_implementing_secrets_scanning_in_ci_cd
name: Implementing Secrets Scanning in CI/CD
description: Embed secret scanning across the CI/CD pipeline — pre-commit, PR checks, pipeline secret hygiene, and leaked-secret response automation.
risk: info
permissions: []
requires_confirmation: false
tags: [secrets, devsecops, ci-cd, scanning]
version: 1.0.0
---
## Purpose

Make the delivery pipeline a place where secrets are caught, not leaked. This playbook layers secret scanning at every CI/CD stage — pre-commit hooks, pull-request checks, pipeline-definition scanning, container-image layer scanning — while fixing the pipeline's own secret hygiene (masked logs, scoped tokens, OIDC instead of stored credentials), so the system that ships software doesn't also ship its keys.

## When to use

- Preventing secrets from entering repositories via the development workflow.
- Auditing CI/CD pipelines that currently use long-lived stored credentials.
- Meeting supply-chain security expectations (SLSA, EO 14028, SOC 2).
- After incidents where leaked CI secrets enabled code or infrastructure compromise.
- Standardizing secret handling across many teams' pipelines.

## Prerequisites

- Inventory of CI/CD platforms (GitHub Actions, GitLab CI, Jenkins, etc.) and their secret-storage mechanisms.
- Secret-scanning tooling selected per stage (gitleaks, trufflehog for history depth, platform-native scanning).
- Defined secrets-management target: where pipeline secrets should live (Vault, cloud secret managers, platform secret stores with OIDC).
- Revocation runbook and authority for each secret type the pipelines use.
- Baseline scan of pipeline definitions and history before enforcement.

## Procedure

1. **Scan pipeline definitions as code.** CI configs (`.github/workflows/`, `.gitlab-ci.yml`, Jenkinsfiles) are prime secret-hiding spots. Run secret scanners over pipeline definitions in CI, failing on findings. Pay special attention to inline credentials in scripts, hardcoded tokens in `curl` commands, and base64 blobs that decode to keys.
2. **Enforce pre-commit and PR scanning.** Deploy pre-commit hooks (gitleaks/trufflehog) for developers and mandatory PR checks scanning the diff. The PR check is the enforcement point developers can't skip with `--no-verify`. Complement with platform-native secret scanning (GitHub secret scanning with push protection is the gold standard where available — it blocks the push, not just the PR).
3. **Scan history and container layers.** Run full-history scans on schedule (trufflehog's strength is finding secrets across git history with verification), and scan built container images for secrets in layers — a secret `COPY`ed into a layer persists even if deleted in a later layer. Fail image builds containing secrets.
4. **Fix pipeline secret hygiene.** Migrate pipelines to OIDC federation (GitHub Actions → AWS/GCP/Azure via OIDC, no stored cloud credentials), scope tokens minimally (per-job, per-environment), mask secrets in logs (verify masking actually works — multiline secrets and transformed values leak past naive masking), and rotate any long-lived pipeline credential on a schedule with an owner.
5. **Protect the secret stores.** Restrict who can read and modify CI secret stores (they're credential vaults with a web UI), require approvals for production-environment secret changes, and audit secret access. A compromised CI admin can exfiltrate every secret the pipelines can reach — scope pipeline identities to least privilege.
6. **Automate the leak response.** On confirmed secret detection in the pipeline: automatically revoke/rotate the secret (where safe automation exists), open a tracked incident, audit usage logs for the exposed credential, and notify the owner. Speed beats process elegance — the window between leak and exploitation is measured in minutes for high-value keys.
7. **Provide the paved path.** Give developers and pipeline authors the blessed patterns: referencing secrets from the manager (never inline), OIDC-based cloud auth templates, and local-dev secret provisioning. Every blocked secret should come with a link to the right way, not just an error.
8. **Measure and govern.** Track: secrets blocked per month (trending down is the goal), mean time to revoke leaked secrets, % of pipelines on OIDC vs. stored credentials, and scan coverage across repos. Review quarterly with engineering leadership; celebrate teams hitting zero.

## Expected outputs

- Secret scanning at pre-commit, PR, pipeline-definition, and image-layer stages.
- OIDC-based pipeline authentication replacing stored credentials; scoped, masked, rotated secrets.
- Hardened CI secret stores with access auditing.
- Automated leak-response runbook with revocation procedures.
- Metrics: blocked secrets, revocation MTTR, OIDC adoption, coverage.

## Pitfalls

- **Push protection gaps.** PR-only scanning misses direct pushes to main and force-pushes. Enable push protection (or equivalent) where the platform supports it — it's the strongest control in this stack.
- **Masking theater.** Secret masking that fails on multiline values, substrings, or transformed secrets leaks credentials into build logs that persist indefinitely. Test masking adversarially.
- **Over-scoped pipeline tokens.** A workflow token with write access to everything the repo can reach turns any compromised workflow into full compromise. Scope per job, per environment, minimally.
- **Secrets in image layers.** Multi-stage builds that `COPY` secrets in early stages bake them into layer history. Use build secrets (BuildKit `--secret`) that never persist in layers, and scan final images.
- **Alert fatigue on historical findings.** Failing every build on five-year-old triaged findings trains teams to disable the scanner. Separate new-findings enforcement from historical-finding remediation backlogs.

## References

- GitHub secret scanning and push protection documentation — https://docs.github.com/en/code-security/secret-scanning
- TruffleHog documentation — https://trufflesecurity.com/trufflehog
- SLSA framework (build integrity) — https://slsa.dev/
- MITRE ATT&CK T1552 (Unsecured Credentials) — https://attack.mitre.org/techniques/T1552/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
