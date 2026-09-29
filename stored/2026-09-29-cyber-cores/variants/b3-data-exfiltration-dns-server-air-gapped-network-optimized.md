---
skill_id: cyber_b3_data_exfiltration_dns_server_air_gapped_network_optimized
name: Data Exfiltration Defense for DNS Servers in Air-Gapped Networks (Optimized Maturity)
description: "Data Exfiltration defense playbook for DNS Servers in Air-Gapped Networks at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [exfiltration, dlp, network, dns, air-gap, ot, high-security, maturity-optimized]
version: 1.0.0
---
# Data Exfiltration Defense for DNS Servers in Air-Gapped Networks (Optimized Maturity)

## Purpose

Sensitive data leaving the network — the moment an intrusion becomes a breach. Quantifying WHAT left is more important than blocking the channel after the fact; notification obligations depend on the data, not the technique. Applies to DNS Servers in Air-Gapped Networks at Optimized maturity.

## When to use

- Egress spikes: large uploads to external hosts, cloud storage, or paste sites from servers that normally receive more than they send.
- Staging activity: large archives (zip/7z/rar) created in temp directories, database dumps, or mailbox exports shortly before the transfer.
- DLP alerts on regulated data patterns (SSN, card numbers, PHI formats) in outbound traffic, or DNS/ICMP exfil at low volume.
- Lens: Best telemetry: query logs (or passive DNS) + zone-transfer/change audit + resolver cache stats. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in DNS query logs showing tunneling/DGA patterns; zone files and their change history and Zone-transfer (AXFR) request logs; DNSSEC validation failure logs; run `grep -E '.{60,}' /var/log/named/query.log | tail -20   # long labels: tunneling/DGA` then `rndc status; echo ---; journalctl -u named --since '1 hour ago' | grep -iE 'transfer|denied|error' | tail -15`.
3. **Analyze.** Reconstruct the exfil set: source paths, file types, record counts, and data classification — involve legal early for notification scoping. Then: Preserve full packet/proxy logs of the transfer; they prove what left and are evidence for regulators and law enforcement.
4. **Contain and harden.** DLP policies with blocking on bulk sensitive-data egress, plus alerting on archive creation and database dump commands. Asset layer: Restrict recursion to internal clients, block outbound port 53 except resolvers, DNSSEC validation on. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the transfer but never determining what was in it — you cannot scope a breach on 'we blocked something'.
- Forgetting cloud audit logs: exfil via sanctioned SaaS (personal Drive, Dropbox) bypasses network DLP.

## References

- MITRE ATT&CK: T1048 (Exfiltration Over Alternative Protocol)
- Vendor logging and hardening baselines for DNS Servers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
