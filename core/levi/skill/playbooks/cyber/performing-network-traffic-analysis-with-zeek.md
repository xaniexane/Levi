---
skill_id: cyber_performing_network_traffic_analysis_with_zeek
name: Network Traffic Analysis with Zeek
description: Hunt through Zeek connection, DNS, HTTP, and file logs to detect C2, exfiltration, and lateral movement.
risk: low
permissions: []
requires_confirmation: false
tags: [network, zeek, hunting]
version: 1.0.0
---

## Purpose
- Use Zeek's rich protocol logs to hunt threats at scale without storing full packet payloads.
- Correlate across log types so a DNS anomaly, an odd connection, and a downloaded file tell one story.
- Build repeatable hunt queries the SOC can rerun on new data.
- Reduce reliance on full packet capture by getting most investigative value from metadata.

## When to use
- When Zeek logs are available from network sensors and an incident or hunt is underway.
- When full packet capture is unavailable but connection-level evidence is needed.
- When building proactive threat hunts for beaconing, tunneling, or data staging.
- When tuning NDR or SIEM detections with protocol-level ground truth.

## Prerequisites
- Access to Zeek logs for the relevant sensors and time range, in a queryable store or on disk.
- Understanding of Zeek log schemas: conn, dns, http, ssl, files, and notice logs at minimum.
- Threat-intel context and baseline knowledge of normal traffic for the monitored network.
- Time synchronization between Zeek sensors and other log sources.

## Procedure
1. Confirm log coverage for the incident window: which sensors, any gaps, and the Zeek version that generated them.
2. Start with conn logs around suspect hosts, examining duration, byte counts, and connection states for long-lived or odd sessions.
3. Review dns logs for high-entropy queries, low TTL abuse, rare record types, and NXDOMAIN bursts suggesting tunneling or DGA.
4. Review http and ssl logs for unusual user agents, rare JA3 hashes, self-signed certificates, and odd SNI values.
5. Pivot through the files log to find downloads and uploads, checking MIME mismatches and hashes against threat intel.
6. Check notice and weird logs for protocol violations and policy hits the sensor already flagged.
7. Analyze x509 logs for certificate anomalies: short validity, unusual issuers, and reused certificates across unrelated hosts.
8. Correlate findings across logs into a session narrative, then validate against endpoint and proxy data.
9. Save hunt queries with descriptions and false-positive notes so the SOC can operationalize them.
10. Document sensor limitations and encrypted-traffic blind spots in the final report.

## Expected outputs
- A Zeek-based hunt report with correlated findings across log types.
- Reusable hunt queries with documented baselines and false-positive handling.
- IOCs and session timelines for the incident case file.
- Tuning recommendations for Zeek notice policies and downstream detections.

## Pitfalls
- Hunting without a baseline; Zeek flags odd-but-normal traffic on every network, so know what normal looks like first.
- Ignoring log gaps from sensor restarts or disk pressure, which create false negatives.
- Treating JA3 or certificate hits as convictions; they are leads that need corroboration.
- Forgetting that Zeek sees only what the sensor sees; asymmetric routing and encryption limit visibility.

## References
- Zeek documentation, https://docs.zeek.org/
- MITRE ATT&CK command and control tactics, https://attack.mitre.org/tactics/TA0011/
- Corelight and Zeek community hunting guides
- NIST SP 800-94 Guide to Intrusion Detection and Prevention Systems
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
