---
skill_id: cyber_b3_secrets_in_code_linux_server_azure_cloud_optimized
name: Secrets in Code Defense for Linux Servers in Azure Cloud (Optimized Maturity)
description: "Secrets in Code defense playbook for Linux Servers in Azure Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [devops, secrets, linux, server, cloud, azure, maturity-optimized]
version: 1.0.0
---
# Secrets in Code Defense for Linux Servers in Azure Cloud (Optimized Maturity)

## Purpose

API keys, passwords, and tokens committed to repositories get scraped by attackers (and by every future repo reader). A committed secret is a compromised secret — rotate first, clean history second. Applies to Linux Servers in Azure Cloud at Optimized maturity.

## When to use

- Secret-scanning alerts (push protection or historical scan) flagging keys, tokens, or private keys in commits.
- Anomalous API usage billed to a key that appears in a repository, or commits adding '.env' files.
- Public repository exposure: any secret ever pushed public is considered harvested.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** For each exposed secret: determine its privileges and check usage logs for unauthorized use since exposure. Then: Check git history depth: secrets in old commits are still exposed to anyone with repo access.
4. **Contain and harden.** Rotate the secret FIRST, then purge from history; enable push protection and pre-commit secret scanning. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the commit without rotating — the secret is already copied.
- Scanning only main branch; secrets hide in feature branches, PRs, and forks.

## References

- MITRE ATT&CK: T1552.001 (Credential Access: Credentials In Files)
- Vendor logging and hardening baselines for Linux Servers; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
