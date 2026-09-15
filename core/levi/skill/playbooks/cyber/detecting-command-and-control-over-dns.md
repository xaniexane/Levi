---
skill_id: cyber_detecting_command_and_control_over_dns
name: Detecting Command and Control Over DNS
description: Detect DNS-based C2 with query analysis: tunneling, DGA, low-TTL fast-flux, and covert channel patterns.
risk: info
permissions: []
requires_confirmation: false
tags: [network, dns, c2]
version: 1.0.0
---
## Purpose

Catch command-and-control hiding in DNS — the protocol that firewalls almost always allow. Detect DNS tunneling, domain-generation algorithms, fast-flux infrastructure, and low-and-slow C2 beacons through query-pattern analysis.

## When to use

- Hunting for C2 in environments where DNS is the likely exfiltration/command channel.
- Investigating hosts with suspicious DNS query patterns.
- Building continuous DNS-threat detection for the SOC.
- Validating that DNS security controls (filtering, logging) are effective.

## Prerequisites

- Centralized DNS logs: resolver query logs, firewall DNS logs, or passive DNS capture — with client IP, query name, type, and response.
- Baseline of normal DNS: query volumes per client, common domains, typical record types.
- Threat-intel feeds for domain reputation and DGA family patterns.
- Ability to block at the DNS layer (RPZ, DNS firewall) for response.

## Procedure

1. **Establish the DNS baseline.** Record per-client: queries per hour, unique domains, NXDOMAIN rate, and record-type distribution. DNS is high-volume but highly regular per client — the anomalies (a workstation suddenly querying 10,000 unique domains) are stark against a baseline.
2. **Detect DNS tunneling.** Alert on: unusually long query names, high entropy in subdomains, excessive TXT/NULL record queries, and large query/response size ratios. Tunneling encodes data in queries — the queries look wrong (long, random, frequent) compared to legitimate resolution. Validate with packet capture showing the actual query content.
3. **Detect DGA activity.** Alert on: high NXDOMAIN rates from a single client (the malware cycling through generated domains), queries to domains with DGA-like characteristics (high entropy, unusual TLDs, very recent registration), and burst patterns. Correlate the queried domains against DGA family classifiers where available.
4. **Detect fast-flux and low-TTL abuse.** Alert on domains with very low TTLs combined with rapidly changing A records across diverse ASNs — the fast-flux signature. Legitimate CDNs use low TTLs too, so corroborate with domain age, registration patterns, and threat intel before convicting.
5. **Hunt low-and-slow DNS C2.** Not all DNS C2 is noisy. Look for: regular periodic queries to rare domains (beaconing over DNS), consistent query timing with small jitter, and domains queried by only one or two internal hosts. Join with proxy/firewall logs — DNS C2 often pairs with the initial compromise's other channels.
6. **Correlate with endpoint and intel.** For flagged clients: check EDR for the querying process (which binary is making these queries?), check domain reputation and passive DNS history (when was the domain registered? what else resolved to that IP?), and check for concurrent suspicious activity on the host. The process behind the queries is the malware — find it.
7. **Respond at the DNS layer.** Block malicious domains via DNS RPZ/firewall (sinkhole for intelligence when possible — sinkholing shows you every infected host still trying), isolate the affected hosts, and hunt for additional infections using the same DNS indicators across the fleet. Monitor for the malware shifting to new domains — DGA means the blocklist is always behind.

## Expected outputs

- Baselined DNS query monitoring with detections for tunneling, DGA, fast-flux, and low-and-slow C2.
- Threat-intel and passive-DNS correlation enriching DNS findings.
- DNS-layer blocking (RPZ/sinkhole) with fleet-wide hunting on confirmed indicators.

## Pitfalls

- No DNS logging — the most common gap; you can't detect what you don't log.
- Alerting on volume alone — CDNs and updaters are voluminous; patterns matter.
- Blocking without sinkholing first — you lose visibility into which hosts are infected.
- Ignoring DNS-over-HTTPS — DoH bypasses traditional DNS monitoring; control or monitor DoH endpoints.
- Treating the domain as the incident — find the host, the malware, and the initial access.

## References

- MITRE ATT&CK T1071.004 (Application Layer Protocol: DNS) and T1048.003 (Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol)
- NIST SP 800-81 (Secure Domain Name System Deployment Guide)
- CISA / NSA guidance on DNS security and protective DNS
- Published DGA detection research for classifier approaches
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
