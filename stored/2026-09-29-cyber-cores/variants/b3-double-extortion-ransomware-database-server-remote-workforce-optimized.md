---
skill_id: cyber_b3_double_extortion_ransomware_database_server_remote_workforce_optimized
name: Double-Extortion Ransomware Defense for Database Servers in Remote Workforce (Optimized Maturity)
description: "Double-Extortion Ransomware defense playbook for Database Servers in Remote Workforce at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [malware, ransomware, exfiltration, data, database, remote, endpoint, zero-trust, maturity-optimized]
version: 1.0.0
---
# Double-Extortion Ransomware Defense for Database Servers in Remote Workforce (Optimized Maturity)

## Purpose

Data is exfiltrated BEFORE encryption, so the attacker can leak it even if you restore from backups. The investigation must answer what was stolen, not just what was encrypted — breach notification clocks start on exfiltration. Applies to Database Servers in Remote Workforce at Optimized maturity.

## When to use

- Large outbound transfers (tens of GB) to cloud storage, file shares, or anonymized endpoints in the days before encryption, often via rclone, MEGAsync, or custom tooling.
- Staging directories with archived/renamed sensitive data (databases, file shares zipped) and data-leak-site monitoring hits for your organization name.
- The ransom note references specific stolen files or threatens publication with a countdown timer.
- Lens: Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries and Slow/general query logs around the incident window; new users, roles, or linked servers; run `-- PostgreSQL style:` then `SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;`.
3. **Analyze.** Quantify the exfil: source directories, file types, record counts, and whether regulated data (PII, PHI, card data) was included — this drives notification obligations. Then: Preserve exfiltration logs (proxy, firewall, DLP, cloud audit) as evidence; they are also the proof of what did and did not leave.
4. **Contain and harden.** DLP egress policies on sensitive data stores plus alerting on bulk archive creation and large outbound transfers. Asset layer: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring victory after restoring from backup while stolen data sits on a leak site — the extortion continues.
- Starting the notification clock at encryption time instead of at first confirmed exfiltration.

## References

- MITRE ATT&CK: T1486 + T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for Database Servers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
