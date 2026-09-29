---
skill_id: cyber_b3_data_exfiltration_wifi_controller_remote_workforce_foundational
name: Data Exfiltration Defense for Wireless Controllers in Remote Workforce (Foundational Maturity)
description: "Data Exfiltration defense playbook for Wireless Controllers in Remote Workforce at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [exfiltration, dlp, network, wireless, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Data Exfiltration Defense for Wireless Controllers in Remote Workforce (Foundational Maturity)

## Purpose

Sensitive data leaving the network — the moment an intrusion becomes a breach. Quantifying WHAT left is more important than blocking the channel after the fact; notification obligations depend on the data, not the technique. Applies to Wireless Controllers in Remote Workforce at Foundational maturity.

## When to use

- Egress spikes: large uploads to external hosts, cloud storage, or paste sites from servers that normally receive more than they send.
- Staging activity: large archives (zip/7z/rar) created in temp directories, database dumps, or mailbox exports shortly before the transfer.
- DLP alerts on regulated data patterns (SSN, card numbers, PHI formats) in outbound traffic, or DNS/ICMP exfil at low volume.
- Lens: Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Client association, authentication (EAP) and roaming logs with device MACs and Rogue AP / evil-twin detections and deauth-flood alerts from WIDS; run `# conceptually (vendor CLIs differ):` then `show wireless client summary | include <suspect-mac>`.
3. **Analyze.** Reconstruct the exfil set: source paths, file types, record counts, and data classification — involve legal early for notification scoping. Then: Preserve full packet/proxy logs of the transfer; they prove what left and are evidence for regulators and law enforcement.
4. **Contain and harden.** DLP policies with blocking on bulk sensitive-data egress, plus alerting on archive creation and database dump commands. Asset layer: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the transfer but never determining what was in it — you cannot scope a breach on 'we blocked something'.
- Forgetting cloud audit logs: exfil via sanctioned SaaS (personal Drive, Dropbox) bypasses network DLP.

## References

- MITRE ATT&CK: T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for Wireless Controllers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
