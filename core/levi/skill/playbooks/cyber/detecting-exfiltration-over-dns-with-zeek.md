---
skill_id: cyber_detecting_exfiltration_over_dns_with_zeek
name: Detecting Exfiltration over DNS with Zeek
description: Hunt DNS exfiltration in Zeek logs with query analytics, entropy scoring, and endpoint correlation.
risk: info
permissions: []
requires_confirmation: false
tags: [dns, exfiltration, zeek]
version: 1.0.0
---
## Purpose

Use Zeek's DNS logs (`dns.log`) as the exfiltration-hunting dataset: query-name analytics, entropy scoring, and volume analysis tuned to your network, correlated with endpoint data to find the exfiltrating process. Zeek sees the DNS your resolvers might not log.

## When to use

- Hunting DNS exfiltration with Zeek already deployed on egress.
- Building continuous Zeek-based DNS anomaly detection.
- Investigating a host flagged for suspicious DNS behavior.
- Validating DNS-layer DLP coverage.

## Prerequisites

- Zeek sensors on egress paths with `dns.log` centralized and retained 30+ days.
- `conn.log` from the same sensors for flow correlation; EDR on endpoints for process attribution.
- Baseline of normal DNS per subnet/client type.
- DNS blocking/sinkholing capability for response.

## Procedure

1. **Extract the DNS feature set from dns.log.** For each (client, query) pair, compute: query count, unique query names, average query-name length, average entropy, query-type distribution, and NXDOMAIN ratio. Zeek's `dns.log` gives you `query`, `qtype_name`, `rcode_name`, and timing — everything needed for exfiltration analytics.
2. **Score for exfiltration indicators.** Flag clients with: high average query length (>80 chars), high entropy subdomains, TXT/NULL query ratios far above baseline, large numbers of unique subdomains under one parent domain (chunked exfiltration), and sustained query streams. Combine into a composite score — single indicators are noisy, the combination is not.
3. **Hunt the long tail of rare domains.** List domains queried by only one or two internal clients with high query counts. Legitimate rare domains get occasional queries; exfiltration domains get thousands from one host. Enrich with domain age and registration data — young domains in this list are high priority.
4. **Analyze timing patterns.** Exfiltration often shows: regular intervals (automated chunking), business-hours-only patterns (blending in), or burst patterns (bulk theft). Compare inter-query timing against the client's normal DNS rhythm — automated exfiltration has a mechanical regularity that human browsing lacks.
5. **Correlate with conn.log and endpoint data.** Join flagged DNS with: `conn.log` for the same client (what else was it doing?), EDR for the querying process (which binary generated these queries?), and file-access telemetry (was it reading sensitive files before the DNS burst?). The Zeek data finds the channel; the endpoint data finds the malware.
6. **Validate with query decoding.** For top suspects, capture full query names and decode: look for encoded file contents, chunk sequencing, and session markers. Confirming your data in the queries converts a statistical suspicion into a breach scope — preserve the evidence for the incident record.
7. **Respond and measure.** Sinkhole the exfiltration domains to enumerate all affected hosts, block at the DNS layer, isolate hosts, and scope the loss (bytes estimated from query volumes, timeframe, files accessed). Afterward, tune the scoring thresholds based on the true positive — every real exfiltration improves the detector.

## Expected outputs

- A Zeek-based DNS exfiltration scoring pipeline (length, entropy, type, volume, rarity) with composite thresholds.
- Endpoint correlation procedures attributing DNS to processes.
- Sinkhole-first response with data-loss scoping and detector tuning from true positives.

## Pitfalls

- Analyzing dns.log without baselines — every network has legitimate weird DNS; know yours.
- Single-indicator alerting — length alone or entropy alone generates noise; composite scoring is the method.
- Short log retention — exfiltration hunting needs weeks of history.
- Blocking before sinkholing — you lose the affected-host enumeration.
- Ignoring DNS-over-HTTPS — Zeek sees port-53 DNS; DoH needs separate handling.

## References

- Zeek documentation (zeek.org) — dns.log fields and scripting
- MITRE ATT&CK T1048.003 (Exfiltration Over Alternative Protocol)
- Published DNS-exfiltration detection research (entropy and analytics methods)
- NIST SP 800-81 (Secure DNS Deployment Guide)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
