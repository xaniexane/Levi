---
skill_id: cyber_analyzing_dns_logs_for_exfiltration
name: Analyzing DNS Logs for Exfiltration
description: Detect DNS tunneling and exfiltration: entropy, query volume, and rare record types.
risk: low
permissions: []
requires_confirmation: false
tags: [network]
version: 1.0.0
---
# Analyzing DNS Logs for Exfiltration

## Purpose

Detect data exfiltration over DNS — tunneling, oversized queries, encoded
labels, and beaconing to attacker-controlled domains — using DNS query logs;
scope how much data plausibly left through the channel; and convert findings
into DNS-layer blocks and durable analytics.

## When to use

- Investigating suspected data theft where normal egress (HTTP, email,
  cloud) shows nothing — DNS is the classic fallback channel.
- Threat hunting: routine sweeps for tunneling signatures in resolver logs.
- Incident response: a compromised host is present and you need to rule DNS
  exfiltration in or out.
- Validating DNS-layer controls (RPZ, DNS firewalling, resolver policy)
  actually see and block malicious queries.
- Post-compromise assurance: confirming no DNS channel operated during the
  dwell window.

## Prerequisites

- Written authorization from the network/data owner to analyze DNS logs
  (queries reveal browsing and application behavior — privacy-sensitive,
  handle minimization applies).
- Chain-of-custody notes: log source (which resolvers/sensors), time range,
  export hashes for evidence-grade findings.
- Centralized DNS query logs: resolver logs, DNS firewall logs, or Zeek
  `dns.log` — with query name, query type, client IP, and timestamp at
  minimum. Response data and TTLs help but aren't required.
- Baseline of normal DNS: top queried domains, normal query-type
  distribution, known high-entropy legitimate services (AV telemetry,
  software updaters, DNS-based blocklists), and sanctioned tunneling tools.

## Procedure

1. **Confirm log coverage and sensor placement.** Verify logs come from resolvers all clients actually use — hosts with hardcoded external DNS bypass your resolver logs entirely; firewall logs of port-53 egress (and DoH/DoT port-443 to known resolver IPs) catch those. Document the blind spots *before* hunting, and state them in every report.
2. **Hunt oversized and high-entropy queries.** DNS labels max out at 63 characters and full names at 253; exfiltration needs volume, so it uses long labels. Compute per (client, domain): average query-name length, label entropy (Shannon), and label counts. Rank outliers. Encoded data looks random; legitimate long names (CDN sharding, telemetry) look structured — learn the difference from your baseline.
3. **Hunt tunneling by query type and volume.** Flag: TXT and NULL record queries from non-standard clients (legitimate TXT uses like SPF/DKIM are server-side and predictable — client TXT bursts are not); high query rates to a single domain from one client; and domains receiving queries but never appearing in legitimate browsing (check against proxy logs — tunneled domains don't show up as web visits, which is itself a signal).
4. **Check for beacon-regular DNS.** Extract inter-query timing per (client, domain). Malware DNS beacons show tight periodicity; combine with the entropy/size signals — periodic + high-entropy + long-label is a strong composite indicator that individual weak signals can't match.
5. **Investigate newly observed and rare domains.** Rank domains by first-seen recency and query count. A domain first seen yesterday receiving thousands of long-label queries from one host is worth immediate investigation: check registration age, passive DNS history, and whether any legitimate software claims it. Newly registered + high-entropy + single-client is the exfiltration trifecta.
6. **Decode a sample before declaring.** Capture the suspect queries and attempt to decode the label content (common encodings: base32/base64/hex, sometimes with custom alphabets or compression). Successful decoding to recognizable data (file fragments, hostnames, usernames, keystrokes) confirms exfiltration; failure to decode doesn't clear it, but changes your confidence language and next steps (endpoint analysis becomes primary).
7. **Estimate data volume.** Count queries × approximate bytes-per-query (label bytes minus encoding overhead, roughly 60–75% efficiency for base64-ish schemes) over the channel's lifetime. This is an upper bound, not a precise measure — report it as such when scoping breach notification, and let legal decide how to characterize it.
8. **Correlate with the endpoint.** Confirm the suspect client was compromised or running the tunneling process: EDR process history showing which process issued the queries, persistence mechanisms, and the initial access vector. DNS logs tell you *what left*; the endpoint tells you *how* — you need both for the incident narrative.
9. **Contain at the DNS layer.** RPZ-block or DNS-firewall-block the malicious domains, force affected hosts to internal resolvers (block direct port-53 egress except from approved resolvers at the firewall), isolate the compromised endpoints, and monitor for fallback: new domains with the same query characteristics, or the same pattern shifting to DoH/DoT.
10. **Deploy durable analytics.**
    Scheduled queries: daily top-(client, domain) by average query length
    and entropy; new-domain watchlist with age and volume thresholds;
    TXT/NULL anomaly detection; beacon-regularity scoring.
    Tune against the legitimate high-entropy services baselined in the
    prerequisites, and review tuning quarterly as the SaaS footprint
    changes.

## Key tools & commands

- Zeek `dns.log` — the gold standard for DNS hunting (query, qtype,
  answers, TTLs, response codes); most analytics assume this schema.
- Resolver/DNS-firewall logs (Infoblox, BIND query log, DNSFilter, Cisco
  Umbrella) — aggregated views with policy-enforcement history.
- Your SIEM or notebook environment — implement the (client, domain)
  length/entropy/rank aggregations in whatever you query with; the logic
  matters more than the syntax.
- `dig` / passive DNS / WHOIS — investigating suspect domains' registration
  age and resolution history.
- Base64/base32/hex decoders and entropy calculators — the manual decode
  step; script the common cases once you've seen them.

## Expected outputs

- Hunt findings: suspect (client, domain) pairs with size/entropy/timing
  evidence, first-seen data, and confidence ratings.
- Decoded sample content where possible, with methodology and confidence
  noted.
- Data-volume upper-bound estimate for impact scoping, with stated
  assumptions.
- Containment actions (RPZ blocks, egress policy changes, host isolation)
  and fallback monitoring results.
- Scheduled detection queries with tuning documentation.

## Pitfalls

- Legitimate high-entropy DNS is everywhere (antivirus cloud lookups, CDN
  domain sharding, software telemetry, DNSBLs). Allowlists built from
  observed legitimate services are mandatory — entropy alone is not a
  detection, it's a triage feature.
- DoH/DoT bypasses resolver logs entirely; if your environment allows
  direct 443 to external resolvers, your DNS logs have a hole. Address the
  egress policy (block or proxy external DoH), not just the analytics.
- Short-lived exfiltration bursts hide in daily aggregates — run both
  high-frequency (hourly) and long-window analyses.
- Attributing queries to users instead of hosts: DNS is per-host (often
  per-NAT) telemetry. Combine with DHCP/identity logs before naming a
  person, and be careful with shared/VDI hosts.
- Forgetting response-side analysis: NXDOMAIN-heavy patterns indicate DGA
  rather than tunneling — different playbook, different response. Check the
  response codes.

## References

- MITRE ATT&CK: T1048.003 (Exfiltration Over Unencrypted/Obfuscated
  Non-C2 Protocol — DNS), T1071.004 (DNS as C2), T1132 (Data Encoding),
  T1568 (Dynamic Resolution — for DGA-adjacent patterns)
- Zeek DNS log documentation (field reference for hunting)
- SANS / community DNS-tunneling detection write-ups (entropy, length, and
  timing analytics)
- IETF DNS parameters (label/name length limits grounding the size
  heuristics)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
