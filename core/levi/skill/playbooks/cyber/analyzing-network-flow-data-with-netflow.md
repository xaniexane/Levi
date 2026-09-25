---
skill_id: cyber_analyzing_network_flow_data_with_netflow
name: Analyzing Network Flow Data with NetFlow
description: Hunt lateral movement and exfiltration in NetFlow/IPFIX records.
risk: low
permissions: []
requires_confirmation: false
tags: [network]
version: 1.0.0
---
# Analyzing Network Flow Data with NetFlow

## Purpose

Use NetFlow/IPFIX flow records to reconstruct who talked to whom, when, and how much — hunting lateral movement, data exfiltration, and C2 beaconing across time windows where full packet capture does not exist.

## When to use

- An incident spans days or weeks; pcaps are long gone but flow collectors (router/switch exports) retain history.
- You need network-wide visibility: which internal hosts contacted an external IOC, or which hosts a compromised box touched.
- Validating firewall/proxy logs with an independent telemetry source.

## Prerequisites

- Written authorization; define the incident time window and the scope (subnets, hosts) in the case record.
- Access to the flow collector (e.g., nfdump files, SiLK repository, or a commercial NMS) covering the window.
- List of known IOCs (IPs, ports) and baseline knowledge of normal traffic for the environment.
- Timezone discipline: record whether flow timestamps are UTC or collector-local.

## Procedure

1. Confirm collector coverage for the incident window: check the earliest and latest flow timestamps in the repository before drawing conclusions about "no traffic."
2. Pull flows for the suspect host across the full window:
   `nfdump -r nfcapd.current -o "fmt:%ts %td %sa %da %sp %dp %pr %byt %pkt" "host 10.1.5.23"`
   Adjust the filter to `net` or multi-host as scope expands.
3. Build a top-talkers summary to spot anomalies:
   `nfdump -r nfcapd.current -s ip/bytes -o csv "host 10.1.5.23" | head -40`
   Flag external destinations with disproportionate byte counts (exfiltration) or tiny-but-frequent flows (beaconing).
4. Hunt beaconing: aggregate flows by (src, dst, dport) and examine inter-flow timing regularity:
   `nfdump -r ... -o "fmt:%ts %sa %da %dp %byt" "host 10.1.5.23 and dst port 443" | sort`
   Fixed intervals with low jitter over days is a strong C2 indicator.
5. Hunt exfiltration: sort by bytes outbound to external addresses:
   `nfdump -r ... -s dstip/bytes -o csv "src 10.1.5.23 and not dst net 10.0.0.0/8"`
   Compare against the host's historical baseline; off-hours spikes matter.
6. Trace lateral movement: list internal destinations the host contacted, especially admin ports:
   `nfdump -r ... -o "fmt:%ts %da %dp" "src 10.1.5.23 and dst net 10.0.0.0/8 and (dst port 445 or dst port 3389 or dst port 22)"`
   New SMB/RDP/SSH edges from a workstation to servers warrant host-level follow-up.
7. Pivot: for each suspicious external IP, find every internal host that talked to it:
   `nfdump -r ... "dst host 203.0.113.45" -s srcip/bytes`
   This scopes the incident beyond the first host.
8. Check DNS-adjacent flows: large UDP/53 byte counts to non-corporate resolvers suggest tunneling; correlate with DNS logs.
9. Correlate flow findings with proxy, firewall, EDR, and authentication logs for the same timestamps before declaring IOCs.
10. Detect data staging: look for large internal-to-internal transfers that precede external exfiltration — attackers often consolidate loot on one host before sending it out.
11. Run a baseline-deviation check: compare the window's per-host external byte counts against the prior 30-day average from the collector, and document the comparison method so it is defensible.
12. Identify C2 fallback infrastructure: secondary destinations showing beaconing patterns similar to the primary C2.
13. Check for internal scanning: one internal host touching many internal hosts on a single port suggests reconnaissance or worm-like spread — pivot to host forensics.
14. Correlate with DHCP logs to resolve address-to-host mappings across the full window before naming machines in the report.
15. Export the evidence flows with hashes:
    `nfdump -r nfcapd.current -w evidence_flows.nfcapd "host 10.1.5.23"`
    and record the exact filter used so the result is reproducible.

## Key tools & commands

- `nfdump -r <file> "<filter>"` — read and filter NetFlow v5/v9/IPFIX captures.
- `nfdump -s ip/bytes -o csv` — top-talker aggregation by bytes.
- `nfdump -w <out>` — write filtered evidence subset.
- `nfcapd` — the collector daemon producing the raw files.
- SiLK (`rwfilter`, `rwstats`) — alternative flow analysis suite for large repositories.
- `nfdump -A srcip,dstip` — aggregate flows to cut noise on busy hosts.
- `rwstats --top` — SiLK top-N reports by bytes, packets, or flows.
- `whois` / ASN lookups — attributing external destinations.
- DHCP logs — mapping addresses back to hosts when DHCP churn exists.
- Flow exporters: router/switch NetFlow config, `softflowd`/`fprobe` for hosts without hardware export.

## Expected outputs

- Evidence flow files with hashes and the exact reproducing filter.
- Beaconing analysis: interval, jitter, duration, destination.
- Exfiltration assessment: bytes, destinations, time windows vs. baseline.
- Lateral-movement edge list: source → destination:port with first/last seen.
- Baseline-deviation table: incident-window volumes vs. 30-day average per host.
- Data-staging candidates: internal hosts with large inbound-then-outbound patterns.
- Scoping memo: all internal hosts touching each confirmed-bad external IP.

## Pitfalls

- Assuming "no flows" means "no traffic" — check collector coverage and exporter outages first.
- Ignoring NAT: flows show post-NAT addresses; map back to internal hosts via NAT logs.
- Timezone mistakes when correlating flows with logs — normalize everything to UTC in the case file.
- Sampling: many exporters sample 1:1000; low-volume beacons can vanish — note the sampling rate in findings.
- Treating byte counts as exact exfiltration proof — flows lack payload; pair with proxy/DLP logs for content confirmation.
- Daylight-saving shifts in collector timestamps creating phantom gaps or duplicates.
- Aggregated exports hiding low-volume beacons inside high-volume legitimate traffic.
- DHCP churn misattributing an address to the wrong host — join with DHCP logs before naming a machine.
- Exporter clock drift — validate timestamps against a known event before trusting ordering.
- Encapsulated traffic (MPLS/VXLAN): inner headers are invisible to the exporter — note it in findings.
- Asymmetric routing: return traffic may pass a different exporter — check both directions.
- Short flow timeouts splitting long sessions — reassemble by 5-tuple before beacon analysis.
- Collector disk-full gaps misread as quiet periods — check collector health logs.

## References

- nfdump documentation: https://github.com/phaag/nfdump
- SiLK documentation: https://tools.netsa.cert.org/silk/
- RFC 7011 — IPFIX; RFC 3954 — NetFlow v9; RFC 5470 — IPFIX architecture
- MITRE ATT&CK T1041 (Exfiltration Over C2 Channel), T1048 (Exfiltration Over Alternative Protocol), T1021 (Remote Services), T1071 (Application Layer Protocol)
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
