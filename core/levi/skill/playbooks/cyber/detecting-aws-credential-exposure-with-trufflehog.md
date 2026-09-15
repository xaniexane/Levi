---
skill_id: cyber_detecting_aws_credential_exposure_with_trufflehog
name: Detecting AWS Credential Exposure with TruffleHog
description: Scan code, history, and artifacts for exposed AWS credentials with TruffleHog and drive them to rotation.
risk: info
permissions: []
requires_confirmation: false
tags: [aws, secrets, detection]
version: 1.0.0
---
## Purpose

Find AWS access keys (and other secrets) leaked into git history, CI logs, containers, and wikis using TruffleHog's verified-secret scanning — then rotate every exposed credential and close the leak at its source. Detection plus remediation, not just a report.

## When to use

- Auditing repositories and CI pipelines for committed secrets.
- Responding to a suspected credential leak (public repo, paste site, compromised laptop).
- Building secrets-scanning into CI/CD as a preventive gate.
- Periodic credential-hygiene sweeps across the estate.

## Prerequisites

- TruffleHog installed with network access for secret verification (verified findings are the priority).
- An inventory of repositories, CI systems, container registries, and collaboration tools to scan.
- Authority to rotate exposed credentials immediately — scanning without rotation is just documentation of risk.
- A secrets-management solution (AWS Secrets Manager, Vault, or equivalent) to migrate findings into.

## Procedure

1. **Scan git history, not just HEAD.** Run TruffleHog against full repository histories (`--since-commit` from the beginning) — secrets are most often found in old commits, deleted branches, and force-pushed history. Cover all org repos, forks, and mirrors, including private repos (insider leaks and compromised accounts don't respect visibility settings).
2. **Expand beyond git.** Scan: CI/CD logs and artifacts, container images and registries (layers preserve deleted secrets), wikis and tickets (support threads love pasting keys), IaC state files (Terraform state is a credential goldmine — ensure it's encrypted and access-logged), and developer laptops on request during incidents.
3. **Triage verified findings first.** TruffleHog's verified results (keys confirmed live against AWS) are active compromises until proven otherwise — treat each as an incident: determine exposure window from git history, check CloudTrail for unauthorized use of the key, then rotate immediately. Unverified findings get rotated on a schedule, not ignored.
4. **Rotate with a safe sequence.** For each exposed key: create the replacement, update all legitimate consumers, verify the new key works, then deactivate (don't delete — preserve for forensics) the old key. Monitor CloudTrail for any use of the old key after deactivation — post-rotation use means an unknown consumer or an active attacker.
5. **Find the leak's root cause.** For each exposure, determine how the secret got there: hardcoded in code, baked into a container, pasted into a ticket, or logged by a verbose CI step. Fix the mechanism: pre-commit hooks (git-secrets, TruffleHog pre-commit), CI secret masking, `.gitignore` for env files, and container build hygiene (multi-stage builds, no secrets in layers).
6. **Gate the pipeline.** Add secrets scanning as a blocking CI check on every PR and as a scheduled full-history scan. Block merges on verified findings. This converts one-time cleanup into permanent prevention — the scan that found the leak becomes the scan that prevents the next one.
7. **Hunt for exploitation of exposed keys.** For every rotated key, run a CloudTrail lookback over the exposure window: unusual APIs, new resources, data access. If exploitation is found, escalate from hygiene task to incident response. Assume exposed keys are exploited until the logs prove otherwise.

## Expected outputs

- Full-history TruffleHog scans across repos, CI, containers, and wikis with verified findings triaged as incidents.
- Rotated credentials with CloudTrail-verified exposure windows and post-rotation monitoring.
- CI blocking gates and pre-commit hooks preventing recurrence; root causes fixed per finding.

## Pitfalls

- Scanning only the latest commit — the secrets live in history.
- Rotating the key but not checking CloudTrail — you miss the exploitation that already happened.
- Deleting instead of deactivating old keys — you lose the ability to detect continued use.
- Unverified findings deprioritized forever — rotate them too, on a schedule.
- No pipeline gate after cleanup — the same leak recurs within months.

## References

- TruffleHog documentation (trufflesecurity.com) — scanning modes and verification
- AWS documentation — IAM access key rotation best practices
- NIST SP 800-57 (Key Management) — key lifecycle guidance
- MITRE ATT&CK T1552.001 / T1552.005 (Unsecured Credentials: Credentials in Files / Cloud Instance Metadata API)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
