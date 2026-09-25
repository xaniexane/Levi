---
skill_id: cyber_hunting_for_dns_tunneling_with_zeek
name: Hunting for DNS Tunneling with Zeek
description: Detect DNS tunneling and DNS-based C2/exfiltration using Zeek dns.log analysis: query entropy, record-type abuse, and volume anomalies.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, dns, network]
version: 1.0.0
---
## Purpose

DNS tunneling encodes data in DNS queries and responses, turning the
universally allowed DNS protocol into a C2 and exfiltration channel. Zeek's
`dns.log` provides the ideal hunting dataset: full query/response detail
with timing. This playbook covers detecting tunneling through statistical
and behavioral analysis of Zeek DNS telemetry.

## When to use

- Proactive network hunting for covert C2 channels.
- Investigating hosts with suspicious DNS patterns but no obvious
  malware.
- Validating that DNS monitoring would catch tunneling tools.
- After detecting an implant: checking whether DNS was a secondary C2
  channel.

## Prerequisites

- Zeek (or equivalent) DNS logging with query names, query types,
  response codes, TTLs, and timestamps — ideally 30+ days retained.
- Analytical tooling for string-entropy and volume statistics.
- Baselines: normal query rates per host, common query types in the
  environment, and authorized DNS-tunneling-like services (some
  security products legitimately use DNS for lookups).

## Procedure

1. **Profile normal DNS.** Establish per-host and fleet-wide baselines:
   queries per hour, query-type distribution (A/AAAA dominate),
   average query-name length and entropy, and NXDOMAIN rates. Tunneling
   detection is deviation-from-baseline work.
2. **Hunt volume anomalies.** Flag hosts with DNS query volumes far
   above their baseline, especially to a single domain or with
   sustained high rates over hours — tunneling needs many queries to
   move meaningful data.
3. **Hunt record-type abuse.** Tunneling favors TXT, NULL, CNAME, and
   MX records for payload capacity. Alert on hosts with unusual
   proportions of these types, particularly TXT/NULL queries to rare
   domains.
4. **Hunt name-structure anomalies.** Compute query-name entropy and
   length statistics: tunneling subdomains are long, high-entropy, and
   often encode data in the leftmost labels. Flag domains with many
   unique long subdomains from a single host — the classic tunneling
   shape.
5. **Hunt response anomalies.** Check for unusually large DNS responses,
   low TTLs on tunneling domains (fast rotation), and high NXDOMAIN
   rates suggesting domain-generation or probing behavior.
6. **Exclude legitimate DNS-data services.** Security products, DNS
   filtering services, and some SaaS tools legitimately encode data in
   DNS — maintain an allow-list of these domains and validate before
   escalating.
7. **Attribute to the endpoint.** For surviving candidates, identify the
   process generating the queries (endpoint DNS telemetry or Zeek
   correlated with host data). Tunneling tools run as distinct
   processes or injected threads — capture the binary and its
   persistence.
8. **Respond and detect durably.** Block the tunneling domains at the
   resolver/firewall, isolate affected hosts, extract the tool's
   configuration for IOCs, and convert the successful analytics
   (entropy, type-ratio, volume) into scheduled detections.

## Expected outputs

- Tunneling candidates with statistical evidence (volume, entropy,
   type ratios).
- Endpoint attribution: processes and persistence per finding.
- Blocked domains and incident-response handoffs.
- Scheduled DNS-tunneling analytics with tuned thresholds.

## Pitfalls

- Legitimate DNS-based services (threat-intel lookups, some VPNs)
   mimic tunneling statistics — the allow-list is essential.
- Short analysis windows miss low-and-slow tunneling — use maximum
   retention and multi-day persistence requirements.
- Encrypted DNS (DoH/DoT) blinds Zeek's dns.log — ensure policy
   routes DNS through monitored resolvers or log at the endpoint.
- Entropy thresholds need per-environment tuning — start with
   ranking, not hard cutoffs.
- Blocking at the domain level may miss IP-based fallback — check for
   direct-IP DNS and hardcoded resolvers too.

## References

- MITRE ATT&CK: T1071.004 (DNS), T1048.003 (Exfiltration Over
  Unencrypted/Obfuscated Non-C2 Protocol)
- Zeek documentation: dns.log fields and DNS analysis scripts
- NIST SP 800-81: Secure Domain Name System Deployment Guide
- Industry research on DNS tunneling detection techniques
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
