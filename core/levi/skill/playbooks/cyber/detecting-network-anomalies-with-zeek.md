---
skill_id: cyber_detecting_network_anomalies_with_zeek
name: Detecting Network Anomalies with Zeek
description: Build Zeek-based network anomaly detection: baselines, statistical alerts, and notice tuning.
risk: low
permissions: []
requires_confirmation: false
tags: [zeek, anomaly-detection, nsm]
version: 1.0.0
---
## Purpose

Zeek's structured logs are ideal raw material for network anomaly detection — but default notices only scratch the surface. This playbook shows defenders how to build a Zeek-based anomaly capability: selecting the right logs, establishing statistical baselines, writing anomaly detections, and tuning out the noise that kills NSM programs.

## When to use

- Zeek is deployed but only default notices are used — you need real detections.
- Building a network anomaly detection program without a commercial NDR.
- Too many Zeek notices; you need a tuning methodology.
- Threat hunting with Zeek logs needs repeatable anomaly queries.

## Prerequisites

- Zeek sensors covering the segments you care about (east-west for lateral movement, egress for C2/exfil).
- Zeek logs (conn, dns, http, ssl, files, weird, notice) in a queryable store with retention matched to hunt needs.
- Scripting ability: Zeek scripting language basics or a SIEM query language for post-processing.
- Asset and network context: subnets, server roles, expected external services.

## Procedure

1. Start with Zeek's own anomaly signals. Tune weird.log (protocol violations), notice.log (scan detection, Heartbleed-style checks), and the intel framework before building custom analytics. Many deployments ignore these — review what they already catch in your environment and tune thresholds to your traffic before adding complexity.
2. Build connection-baseline analytics on conn.log. Compute per-internal-host baselines: distinct external destinations, bytes in/out ratios, connection durations, and port diversity. Alert on statistical deviations (e.g., z-score or IQR-based) rather than fixed thresholds — fixed thresholds die in heterogeneous networks. A workstation suddenly talking to 500 external IPs, or uploading 10x its baseline, is the classic exfil/C2 pattern.
3. Add DNS and TLS anomaly layers. From dns.log: high query rates, long/entropy-heavy domain names, rare TLDs, and DNS tunneling indicators (large TXT responses, high query volume per domain). From ssl.log: JA3/JA4 anomalies, self-signed or short-lived certs on egress, and certificate age mismatches. These catch C2 that hides in 'normal' HTTPS.
4. Detect lateral and reconnaissance patterns internally. From conn.log: internal port sweeping (one host, many ports), host sweeping (one host, many internal IPs), and new internal services (first-seen port per host). Zeek's scan detection notices help, but custom thresholds tuned to your vulnerability-scanner schedule reduce false positives dramatically.
5. Operationalize with a tuning loop. Every anomaly alert needs: a documented baseline, a threshold rationale, an exclusion list (scanners, updaters, backup systems), and a weekly review of precision. Promote only alerts sustaining acceptable precision; demote the rest to hunt queries. Anomaly detection without a tuning loop becomes alert spam within a month.
6. Package outputs for response. Each promoted detection gets a runbook: which Zeek logs to pivot on (UID correlation across conn/dns/http/ssl/files), how to extract pcaps for the window, and escalation criteria. Train analysts to pivot from notice → conn UID → full session reconstruction.

## Expected outputs

- Tuned Zeek anomaly detections: conn baseline deviations, DNS/TLS anomalies, internal recon — each with baseline and threshold docs.
- Exclusion lists with owners (scanners, updaters, backups) and review cadence.
- Analyst runbook: UID-based pivoting from alert to session reconstruction.
- Precision metrics per detection and a promotion/demotion log.

## Pitfalls

- Fixed thresholds in heterogeneous networks generate endless false positives — use statistical baselines.
- weird.log is noisy by nature; tune per-protocol rather than disabling it wholesale.
- Encrypted traffic limits Zeek to metadata — design detections around endpoints, timing, and volume, not content.
- Short log retention kills anomaly detection; align retention with baseline windows (weeks, not days).
- Anomaly alerts without exclusions for scanners and updaters will be ignored by analysts within weeks.

## References

- Zeek documentation (docs.zeek.org) — scripting, intel framework, log reference; NIST SP 800-94 (IDS/IPS); MITRE ATT&CK TA0011 (Command and Control) — https://attack.mitre.org/tactics/TA0011/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
