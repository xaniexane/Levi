---
skill_id: cyber_b3_data_exfiltration_cicd_runner_multi_cloud_optimized
name: Data Exfiltration Defense for CI/CD Runners in Multi-Cloud (Optimized Maturity)
description: "Data Exfiltration defense playbook for CI/CD Runners in Multi-Cloud at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [exfiltration, dlp, devops, supply-chain, cloud, multi-cloud, maturity-optimized]
version: 1.0.0
---
# Data Exfiltration Defense for CI/CD Runners in Multi-Cloud (Optimized Maturity)

## Purpose

Sensitive data leaving the network — the moment an intrusion becomes a breach. Quantifying WHAT left is more important than blocking the channel after the fact; notification obligations depend on the data, not the technique. Applies to CI/CD Runners in Multi-Cloud at Optimized maturity.

## When to use

- Egress spikes: large uploads to external hosts, cloud storage, or paste sites from servers that normally receive more than they send.
- Staging activity: large archives (zip/7z/rar) created in temp directories, database dumps, or mailbox exports shortly before the transfer.
- DLP alerts on regulated data patterns (SSN, card numbers, PHI formats) in outbound traffic, or DNS/ICMP exfil at low volume.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Reconstruct the exfil set: source paths, file types, record counts, and data classification — involve legal early for notification scoping. Then: Preserve full packet/proxy logs of the transfer; they prove what left and are evidence for regulators and law enforcement.
4. **Contain and harden.** DLP policies with blocking on bulk sensitive-data egress, plus alerting on archive creation and database dump commands. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the transfer but never determining what was in it — you cannot scope a breach on 'we blocked something'.
- Forgetting cloud audit logs: exfil via sanctioned SaaS (personal Drive, Dropbox) bypasses network DLP.

## References

- MITRE ATT&CK: T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for CI/CD Runners; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
