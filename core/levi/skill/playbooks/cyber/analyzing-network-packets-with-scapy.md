# Analyzing Network Packets with Scapy

## Purpose

Parse, dissect, and statistically analyze packet captures programmatically with Scapy — automating the repetitive parts of pcap triage (beacon timing, protocol anomalies, payload inspection) that GUI tools make tedious.

## When to use

- A pcap is too large for manual Wireshark review and you need scripted extraction of fields, flows, and timing.
- You need custom protocol dissection or to test how a parser reacts to malformed packets (defensive parsing validation).
- Crafting packets is limited to your own lab network for testing detections — never scan or probe systems you are not authorized to touch.

## Prerequisites

- Written authorization covering the capture and any lab systems involved.
- Python 3 with Scapy installed (`pip install scapy`); root/Administrator for live capture only.
- The pcap under analysis stored with its hash; work on a copy.
- Lab network isolation if any packet crafting or replay is planned.

## Procedure

1. Load the capture and get basic statistics:
   `pkts = rdpcap("case.pcap")` then `print(len(pkts))`, `pkts.summary()` for a first glance.
2. Build a protocol histogram to see what the capture actually contains:
   count by highest layer per packet; flag unexpected protocols (e.g., LLMNR storms, raw ICMP from user processes).
3. Extract all conversations as (src, dst, sport, dport, proto) tuples with packet/byte counts; sort by bytes to find exfiltration candidates.
4. Reconstruct TCP streams of interest: filter with `pkts.filter(lambda p: p.haslayer(TCP) and p[TCP].dport == 443)` and reassemble payloads in sequence-number order, handling retransmissions.
5. Analyze beacon timing: for each (src → dst:port) flow, collect packet timestamps and compute inter-arrival deltas; report mean, standard deviation, and jitter — low jitter over long durations indicates automated C2.
6. Inspect DNS queries programmatically: extract `DNSQR.qname` for every query, count label entropy and query rates per domain, and flag TXT/NULL types or abnormally long names.
7. Carve files from the capture: reassemble HTTP `Content-Type: application/octet-stream` bodies or FTP-DATA streams, hash the output, and submit to the malware lab — never execute on the analyst host.
8. Detect fragmentation and overlap anomalies: check IP `frag` offsets for overlapping fragments (a classic IDS-evasion technique, T1027-adjacent obfuscation).
9. Validate checksums and flag anomalies: packets with bad TCP/UDP checksums in bulk can indicate crafted traffic or capture artifacts — distinguish the two by checking whether the sender is local.
10. Hunt credential exposure in cleartext protocols: scan reassembled FTP, Telnet, HTTP basic-auth, and SMTP sessions for credential patterns, and record which sessions exposed them — that defines the rotation scope.
11. Detect tunneling over allowed ports: compare payload entropy and packet-size distributions on ports 80/443/53 against baseline — high-entropy DNS TXT answers or uniform 443 packet sizes suggest covert channels.
12. Extract X.509 certificates from TLS handshakes: parse one certificate per flow, flag self-signed, expired, or CN-mismatched certificates, and log issuers as intelligence.
13. Detect port scans and sweeps: count unique (dst, dport) pairs per source over time windows — scripted sweeps stand out clearly from user browsing.
14. Analyze TCP retransmission and RST patterns: aggressive RSTs or SYN-only flows indicate scanning or blocked C2 connection attempts.
15. Extract and review DHCP and ARP traffic: rogue DHCP servers or ARP-spoofing patterns reveal man-in-the-middle positioning.
16. Summarize findings per endpoint: one paragraph per suspicious host — what it did, when, and the evidence — for the incident report.
17. Fingerprint operating systems passively: TCP window sizes, TTL values, and option ordering per host enrich attribution.
18. Look for covert timing channels: analyze inter-packet delay distributions for encoded exfiltration patterns.
19. Validate the script against the baseline pcap first — any "finding" that fires on clean traffic is a bug, not an IOC.
20. Export findings: write IOC lists (IPs, domains, JA3-relevant fields you extracted) and the analysis script itself into the case file so the work is reproducible.
21. If testing a detection, craft the suspect packet pattern in the lab only:
    build with Scapy layers, send with `sendp()` on the lab interface, and confirm your IDS/EDR fires.

## Key tools & commands

- `rdpcap("file.pcap")` / `wrpcap("out.pcap", pkts)` — read and write captures.
- `pkts.filter(lambda p: ...)` and `p.haslayer(DNS)` / `p[DNSQR].qname` — programmatic dissection.
- `sniff(iface="eth0", filter="tcp port 443", count=100)` — live capture (authorized lab only).
- `sendp()` / `sr()` — lab-only packet crafting and probing.
- `pkts.summary()`, `pkts.pdfdump()` — quick overviews.
- `PcapReader("file.pcap")` — iterate huge captures without loading them into RAM.
- `tshark -T json` piped to `jq` — JSON field pipeline for things Scapy parses slowly.
- Python `hashlib` — hashing carved files for the case record.
- `matplotlib` — plotting beacon inter-arrival times for reports.
- Supporting: `tshark` for cross-checking Scapy's parsing, Wireshark for visual confirmation.

## Expected outputs

- Conversation table (endpoints, ports, packet/byte counts) sorted by volume.
- Beacon-timing report per flow: interval mean/stddev, duration, verdict.
- DNS anomaly list: high-entropy names, odd record types, rate outliers.
- Carved files with SHA-256 hashes and lab disposition.
- Credential-exposure list with affected sessions and rotation scope.
- X.509 certificate inventory from TLS handshakes.
- Reproducible Python script committed to the case file.

## Pitfalls

- Running Scapy as root on a production network and accidentally transmitting — default to read-only `rdpcap` analysis.
- Trusting reassembled streams blindly when retransmissions or out-of-order delivery exist; sort by sequence number.
- Confusing capture artifacts (bad checksums from offload, e.g., TSO) with malicious crafting.
- Analyzing an encrypted stream's "content" — characterize metadata (timing, sizes, SNI) instead.
- Forgetting to hash the pcap before and after analysis.
- Loading multi-gigabyte pcaps into RAM with `rdpcap` — use `PcapReader` or pre-filter with tshark.
- TLS 1.3 encrypting handshake details your script expects — design for metadata-only analysis.
- Wrong link-layer type assumptions mis-decoding every packet — check `capinfos` first.
- Scapy's stream reassembly is manual — handle retransmissions and overlaps explicitly in code.
- Malformed packets crashing naive dissectors — wrap parsing in try/except.
- BPF syntax vs. display-filter syntax confusion in `sniff(filter=...)`.
- IPv6 extension headers breaking hardcoded layer offsets — iterate layers instead.
- `wrpcap` appends across runs without labels — keep provenance clear per write.
- Using `sr()`/`sendp()` outside the lab — even a "test" packet to a production host is unauthorized scanning.
- Assuming Scapy's defaults match your interface MTU — mismatches corrupt crafted packets.
- Forgetting `conf.verb = 0` in scripts — noisy output pollutes case logs.
- Parsing captures with a foreign link type without setting the DLT — silent misdecode.
- Hardcoding port numbers in filters instead of variables — brittle triage scripts.
- Not testing on a small pcap slice first — debug on 100 packets, not 10 million.
- Ignoring raw-socket privilege warnings — capture calls fail cryptically without them.
- `rdpcap()` loads the entire capture into memory — use `PcapReader` for multi-GB files.
- Forgetting `conf.verb = 0` floods stdout and slows batch jobs to a crawl.
- Scapy's `sr()` retransmits silently; set `timeout` and `retry` explicitly or scans take forever.
- BPF filter mistakes fail silently — validate with `tcpdump -d` before a long capture.
- On Windows, Scapy needs Npcap in WinPcap-compatible mode or sniffing returns nothing.
- Crafted packets may carry stale checksums after field edits — recalculate before sending.

## References

- Scapy documentation: https://scapy.readthedocs.io
- tcpdump man page — BPF filter syntax reference
- MITRE ATT&CK T1071 (Application Layer Protocol), T1041 (Exfiltration Over C2 Channel), T1027 (Obfuscated Files or Information), T1040 (Network Sniffing)
- Wireshark/tshark field reference for cross-validation

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
