---
skill_id: cyber_b3_secrets_in_code_database_server_on_prem_datacenter_managed
name: Secrets in Code Defense for Database Servers in On-Premises Datacenter (Managed Maturity)
description: "Secrets in Code defense playbook for Database Servers in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [devops, secrets, data, database, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Secrets in Code Defense for Database Servers in On-Premises Datacenter (Managed Maturity)

## Purpose

API keys, passwords, and tokens committed to repositories get scraped by attackers (and by every future repo reader). A committed secret is a compromised secret — rotate first, clean history second. Applies to Database Servers in On-Premises Datacenter at Managed maturity.

## When to use

- Secret-scanning alerts (push protection or historical scan) flagging keys, tokens, or private keys in commits.
- Anomalous API usage billed to a key that appears in a repository, or commits adding '.env' files.
- Public repository exposure: any secret ever pushed public is considered harvested.
- Lens: Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries and Slow/general query logs around the incident window; new users, roles, or linked servers; run `-- PostgreSQL style:` then `SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;`.
3. **Analyze.** For each exposed secret: determine its privileges and check usage logs for unauthorized use since exposure. Then: Check git history depth: secrets in old commits are still exposed to anyone with repo access.
4. **Contain and harden.** Rotate the secret FIRST, then purge from history; enable push protection and pre-commit secret scanning. Asset layer: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the commit without rotating — the secret is already copied.
- Scanning only main branch; secrets hide in feature branches, PRs, and forks.

## References

- MITRE ATT&CK: T1552.001 (Credential Access: Credentials In Files)
- Vendor logging and hardening baselines for Database Servers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
