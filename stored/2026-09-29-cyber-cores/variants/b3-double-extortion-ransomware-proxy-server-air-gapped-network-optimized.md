---
skill_id: cyber_b3_double_extortion_ransomware_proxy_server_air_gapped_network_optimized
name: Double-Extortion Ransomware Defense for Proxy Servers in Air-Gapped Networks (Optimized Maturity)
description: "Double-Extortion Ransomware defense playbook for Proxy Servers in Air-Gapped Networks at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [malware, ransomware, exfiltration, network, proxy, web, air-gap, ot, high-security, maturity-optimized]
version: 1.0.0
---
# Double-Extortion Ransomware Defense for Proxy Servers in Air-Gapped Networks (Optimized Maturity)

## Purpose

Data is exfiltrated BEFORE encryption, so the attacker can leak it even if you restore from backups. The investigation must answer what was stolen, not just what was encrypted — breach notification clocks start on exfiltration. Applies to Proxy Servers in Air-Gapped Networks at Optimized maturity.

## When to use

- Large outbound transfers (tens of GB) to cloud storage, file shares, or anonymized endpoints in the days before encryption, often via rclone, MEGAsync, or custom tooling.
- Staging directories with archived/renamed sensitive data (databases, file shares zipped) and data-leak-site monitoring hits for your organization name.
- The ransom note references specific stolen files or threatens publication with a countdown timer.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Quantify the exfil: source directories, file types, record counts, and whether regulated data (PII, PHI, card data) was included — this drives notification obligations. Then: Preserve exfiltration logs (proxy, firewall, DLP, cloud audit) as evidence; they are also the proof of what did and did not leave.
4. **Contain and harden.** DLP egress policies on sensitive data stores plus alerting on bulk archive creation and large outbound transfers. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring victory after restoring from backup while stolen data sits on a leak site — the extortion continues.
- Starting the notification clock at encryption time instead of at first confirmed exfiltration.

## References

- MITRE ATT&CK: T1486 + T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for Proxy Servers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
