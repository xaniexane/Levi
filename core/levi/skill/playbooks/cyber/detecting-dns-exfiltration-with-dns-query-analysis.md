---
skill_id: cyber_detecting_dns_exfiltration_with_dns_query_analysis
name: Detecting DNS Exfiltration with DNS Query Analysis
description: Detect data exfiltration over DNS with query-size, entropy, and volume analysis on resolver logs.
risk: info
permissions: []
requires_confirmation: false
tags: [dns, exfiltration, detection]
version: 1.0.0
---
## Purpose

Catch data leaving the network inside DNS queries — the exfiltration channel that bypasses most DLP. Analyze resolver logs for the query patterns exfiltration creates: oversized queries, high entropy, and abnormal volumes to rare domains.

## When to use

- Hunting for data exfiltration in environments with DNS logging.
- Investigating a host with anomalous DNS query patterns.
- Building DLP-adjacent detection for the DNS channel.
- Validating that DNS security controls catch exfiltration attempts.

## Prerequisites

- Centralized DNS query logs (resolver, firewall, or passive capture) with client IP, query name, type, timestamp, and response size.
- Baseline of normal DNS per client: query rates, domain diversity, record-type mix.
- Ability to block/sinkhole at the DNS layer for response.
- EDR on endpoints to identify the exfiltrating process.

## Procedure

1. **Baseline normal DNS per client.** Record: queries per hour, unique domains per day, average query-name length, and record-type distribution. Normal DNS is short names, common domains, A/AAAA records. Exfiltration is long names, rare domains, TXT/NULL records — the contrast is sharp once baselined.
2. **Detect oversized and high-entropy queries.** Alert on: query names exceeding ~100 characters, labels with high Shannon entropy (encoded data looks random), and queries with many labels (data chunked across subdomains). Tune thresholds per environment — some legitimate services (anti-spam, telemetry) use long queries; allowlist those specifically.
3. **Detect volume anomalies to rare domains.** Alert on: high query counts to domains queried by few internal hosts, sustained query streams to a single domain (exfiltration sessions), and query rates that dwarf the client's baseline. A workstation sending 50,000 queries to one unknown domain is exfiltrating, not browsing.
4. **Analyze record types and response patterns.** Alert on: excessive TXT/NULL/CNAME queries (the exfiltration record types), large response sizes for TXT queries, and queries with no corresponding legitimate resolution need. Compare against the baseline record-type mix — exfiltration skews it visibly.
5. **Inspect the actual query content.** For flagged domains, examine full query names: look for Base64/Base32-encoded chunks, sequential chunk numbering, and session identifiers. Decode a sample to confirm — seeing your data (or its encoded form) in the queries is definitive. Preserve packet captures for forensics.
6. **Correlate with the endpoint.** Identify the querying process via EDR: which binary is generating these queries? Check for: unknown processes, processes with network behavior inconsistent with their purpose, and concurrent file-access patterns (reading sensitive files before the DNS burst). The process is the malware — the DNS is just its mouth.
7. **Respond at the DNS and host layers.** Sinkhole the exfiltration domain (to enumerate all affected hosts still querying), block at the DNS firewall, isolate the affected hosts, and scope the data loss: which files were accessed, what was the query volume (estimate bytes exfiltrated from query counts and sizes), and what was the timeframe. Treat confirmed exfiltration as a data-breach incident with notification obligations.

## Expected outputs

- Baselined DNS monitoring with detections for oversized/high-entropy queries, volume anomalies, and exfiltration record types.
- Query-content inspection procedures with decode-and-confirm workflows.
- DNS-layer response (sinkhole/block) with data-loss scoping for breach notification.

## Pitfalls

- No DNS logging — the channel is invisible; log first, detect second.
- Thresholds without allowlists — legitimate long-query services generate endless false positives.
- Blocking before sinkholing — you lose the infected-host enumeration.
- Estimating exfiltration volume from query counts alone — validate with content inspection.
- Treating it as a network incident only — the data-loss scoping determines legal obligations.

## References

- MITRE ATT&CK T1048.003 (Exfiltration Over Alternative Protocol)
- NIST SP 800-81 (Secure DNS Deployment Guide)
- CISA guidance on DNS security monitoring
- Published research on DNS exfiltration detection (entropy and size analysis)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
