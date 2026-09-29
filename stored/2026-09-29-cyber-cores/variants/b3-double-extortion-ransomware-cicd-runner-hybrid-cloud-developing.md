---
skill_id: cyber_b3_double_extortion_ransomware_cicd_runner_hybrid_cloud_developing
name: Double-Extortion Ransomware Defense for CI/CD Runners in Hybrid Cloud (Developing Maturity)
description: "Double-Extortion Ransomware defense playbook for CI/CD Runners in Hybrid Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [malware, ransomware, exfiltration, devops, supply-chain, hybrid, cloud, on-prem, maturity-developing]
version: 1.0.0
---
# Double-Extortion Ransomware Defense for CI/CD Runners in Hybrid Cloud (Developing Maturity)

## Purpose

Data is exfiltrated BEFORE encryption, so the attacker can leak it even if you restore from backups. The investigation must answer what was stolen, not just what was encrypted — breach notification clocks start on exfiltration. Applies to CI/CD Runners in Hybrid Cloud at Developing maturity.

## When to use

- Large outbound transfers (tens of GB) to cloud storage, file shares, or anonymized endpoints in the days before encryption, often via rclone, MEGAsync, or custom tooling.
- Staging directories with archived/renamed sensitive data (databases, file shares zipped) and data-leak-site monitoring hits for your organization name.
- The ransom note references specific stolen files or threatens publication with a countdown timer.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Quantify the exfil: source directories, file types, record counts, and whether regulated data (PII, PHI, card data) was included — this drives notification obligations. Then: Preserve exfiltration logs (proxy, firewall, DLP, cloud audit) as evidence; they are also the proof of what did and did not leave.
4. **Contain and harden.** DLP egress policies on sensitive data stores plus alerting on bulk archive creation and large outbound transfers. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring victory after restoring from backup while stolen data sits on a leak site — the extortion continues.
- Starting the notification clock at encryption time instead of at first confirmed exfiltration.

## References

- MITRE ATT&CK: T1486 + T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for CI/CD Runners; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
