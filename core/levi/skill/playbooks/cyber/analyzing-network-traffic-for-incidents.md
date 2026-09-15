# Analyzing Network Traffic for Incidents

## Purpose

Turn raw network evidence — pcaps, flow records, proxy and DNS logs — into an incident timeline: initial access vector, C2 channels, lateral movement, and exfiltration, with every claim tied to a timestamped artifact.

## When to use

- An alert (EDR, IDS, user report) indicates compromise and you need the network half of the story.
- Scoping: determining which hosts and accounts are involved before containment.
- Post-incident review: validating that C2 is dead and no residual beaconing remains.

## Prerequisites

- Written authorization; incident ticket with defined scope and time window.
- Access to pcaps/flow data, DNS logs, proxy logs, and firewall logs covering the window.
- Known-good baselines for the environment (normal egress, normal DNS resolvers, normal admin ports).
- Timezone normalization plan — convert all sources to UTC in the case file.

## Procedure

1. Freeze the scope: list suspect hosts, the incident window (start 24h before first alert), and data sources available. Record gaps explicitly.
2. Pull DNS logs for suspect hosts across the window. Flag: newly observed domains, high query rates, TXT/NULL types, and lookups immediately preceding the alert.
3. Pull proxy/web logs for the same hosts. Flag: POSTs to rare domains, large uploads, non-browser user agents, and requests to IP-literal URLs.
4. If pcaps exist for the window, extract conversations and check for beaconing (fixed intervals, low jitter) and anomalous protocols per the packet-analysis workflow.
5. If only flows exist, run the NetFlow workflow: top talkers, byte-sorted external destinations, lateral-movement edges on 445/3389/22/5985.
6. Build the lateral-movement graph: for each internal connection from a suspect host to another internal host on admin ports, record first-seen, bytes, and direction. Expand one hop and repeat.
7. Correlate with authentication logs: successful logons (4624 type 3/10, or Linux `auth.log`) on the newly touched hosts at matching timestamps confirm movement vs. scanning.
8. Assess exfiltration: sum outbound bytes to external destinations per host, compare to 30-day baseline, and check DLP/proxy for file types and names transferred.
9. Identify the initial-access vector from the earliest network event: phishing-link click (proxy log), exposed-service exploit (firewall + service logs), or VPN anomaly (auth logs).
10. Check email and identity telemetry for the initial-access story: phishing delivery timestamps should precede the first C2 beacon — if they don't, re-examine the access vector.
11. Review outbound email/SMTP logs for data theft via email and for attacker-created mailbox rules; when cloud mail is involved, pivot to the Office 365 audit-log workflow.
12. Assess DNS-tunneling candidates: any host with outsized DNS byte counts gets a dedicated DNS-log deep dive before you close out the network scope.
13. Review VPN and remote-access logs for the window: attacker logons via VPN precede internal movement — confirm the entry account and source IP.
14. Check cloud audit logs if the environment is hybrid: Entra ID sign-ins and M365 audit events fill gaps the on-prem logs miss.
15. Identify data-staging hosts: internal systems with large inbound transfers from multiple hosts before any external exfiltration.
16. Check backup and recovery infrastructure logs: attackers target backups — confirm they weren't touched.
17. Write the executive summary with confidence levels per claim — leadership acts on this, so qualify what's proven vs. suspected.
18. Schedule the lessons-learned review while details are fresh; assign owners to each detection gap.
19. Produce the incident network timeline: timestamp, source, destination, protocol, bytes, and the evidence file each row came from.
20. Validate containment: after isolation, confirm beaconing stops in fresh captures — residual C2 means the scope was wrong.
21. Write detection improvements: IDS signatures, proxy blocks, and EDR network rules for the observed patterns.

## Key tools & commands

- Wireshark/tshark — pcap conversation and protocol analysis.
- nfdump / SiLK — flow-based top talkers, beaconing, and lateral edges.
- Proxy/DNS/firewall log queries (SIEM or direct) — keyed by host and time window.
- `jq` / `grep` / `awk` — log slicing when no SIEM is available.
- Zeek (`zeek -r capture.pcap`) — connection, DNS, HTTP, and file logs from pcaps.
- Suricata EVE JSON reviewed with `jq` — alert and protocol-event correlation.
- `whois` / ASN data — attributing external IPs in the timeline.
- EDR network telemetry — per-host connection timelines confirming flow findings.
- `mergecap` — combining pcaps from multiple sensors into one timeline.

## Expected outputs

- Scoped host list with evidence-grade network timeline (UTC).
- Lateral-movement graph with first-seen timestamps and confirmation status.
- Exfiltration assessment vs. baseline with destination list.
- Initial-access determination with supporting log excerpts.
- Post-containment verification capture showing C2 silence.
- Initial-access evidence chain: delivery → execution → first beacon.
- DNS-tunneling assessment for hosts with outsized DNS volumes.
- Detection gaps and proposed rules.

## Pitfalls

- Starting analysis without confirming data coverage — missing logs get misread as "nothing happened."
- Mixing timezones across sources, creating impossible causal chains.
- Treating every admin-port connection as lateral movement — validate with auth logs.
- Declaring exfiltration on byte counts alone; confirm with proxy/DLP content evidence.
- Containing before scoping is complete — cutting off one host while C2 persists elsewhere.
- Tunnel vision on the first compromised host in both directions — earlier access gets missed, scope gets over-expanded.
- Dismissing low-severity precursor alerts that turn out to be the initial access.
- Declaring "no exfiltration" from flow data alone — flows have no payload.
- Alert fatigue: precursors dismissed before the incident never get re-examined.
- Assuming the first compromised host is the entry point — keep hunting backward in time.
- Over-scoping: adding every host with a single DNS hit without behavioral confirmation.
- Forgetting backup and recovery infrastructure — attackers target it deliberately.
- Presenting byte counts as exfiltration facts to leadership — qualify with confidence levels.
- Skipping the lessons-learned capture while details are still fresh.

See also: analyzing-network-traffic-of-malware.md, analyzing-network-traffic-with-wireshark.md

## References

- MITRE ATT&CK T1071 (Application Layer Protocol), T1021 (Remote Services), T1041 (Exfiltration Over C2 Channel), T1595 (Active Scanning)
- Zeek documentation: https://docs.zeek.org
- CISA incident reporting guidance: https://www.cisa.gov/report
- SANS Incident Handler's Handbook (public)
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
