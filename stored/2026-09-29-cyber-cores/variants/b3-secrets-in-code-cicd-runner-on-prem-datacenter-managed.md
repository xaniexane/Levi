---
skill_id: cyber_b3_secrets_in_code_cicd_runner_on_prem_datacenter_managed
name: Secrets in Code Defense for CI/CD Runners in On-Premises Datacenter (Managed Maturity)
description: "Secrets in Code defense playbook for CI/CD Runners in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [devops, secrets, supply-chain, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Secrets in Code Defense for CI/CD Runners in On-Premises Datacenter (Managed Maturity)

## Purpose

API keys, passwords, and tokens committed to repositories get scraped by attackers (and by every future repo reader). A committed secret is a compromised secret — rotate first, clean history second. Applies to CI/CD Runners in On-Premises Datacenter at Managed maturity.

## When to use

- Secret-scanning alerts (push protection or historical scan) flagging keys, tokens, or private keys in commits.
- Anomalous API usage billed to a key that appears in a repository, or commits adding '.env' files.
- Public repository exposure: any secret ever pushed public is considered harvested.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** For each exposed secret: determine its privileges and check usage logs for unauthorized use since exposure. Then: Check git history depth: secrets in old commits are still exposed to anyone with repo access.
4. **Contain and harden.** Rotate the secret FIRST, then purge from history; enable push protection and pre-commit secret scanning. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the commit without rotating — the secret is already copied.
- Scanning only main branch; secrets hide in feature branches, PRs, and forks.

## References

- MITRE ATT&CK: T1552.001 (Credential Access: Credentials In Files)
- Vendor logging and hardening baselines for CI/CD Runners; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
