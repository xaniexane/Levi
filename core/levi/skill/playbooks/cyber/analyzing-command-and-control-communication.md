---
skill_id: cyber_analyzing_command_and_control_communication
name: Analyzing Command-and-Control Communication
description: Identify C2 channels: beaconing, tunneling, and covert-channel indicators.
risk: low
permissions: []
requires_confirmation: false
tags: [network, threat-intel]
version: 1.0.0
---
# Analyzing Command-and-Control Communication

## Purpose

Detect, characterize, and disrupt adversary command-and-control (C2)
channels by analyzing network communications — identifying beaconing,
tunneling, and covert channels across DNS, HTTP(S), and other protocols —
and converting findings into blocks, detections, and data-impact
assessments.

## When to use

- EDR/SIEM alerts suggest a compromised host is communicating externally
  (or you suspect it and need to prove it).
- Threat hunting for beaconing, DNS tunneling, ICMP tunneling, or data
  staging in network telemetry.
- Incident response: mapping the full C2 infrastructure behind a confirmed
  intrusion.
- Validating egress controls: proving what can actually talk out of your
  network vs. what policy says.
- Post-containment: verifying the adversary's fallback channels are also
  dead.

## Prerequisites

- Written authorization from the network/data owner to capture and inspect
  traffic, including any TLS interception (legal and privacy implications —
  get explicit approval, don't assume it).
- Chain-of-custody notes: capture files hashed, time ranges, sensor
  placement, collector identity, and any decryption keys' handling.
- Network telemetry sources inventoried: NetFlow/IPFIX, DNS logs, proxy
  logs, firewall logs, and full packet capture where available. Know each
  source's retention, sampling rate, and blind spots before promising
  conclusions.
- Baseline knowledge of normal egress: approved external services, update
  infrastructure, SaaS traffic patterns, and sanctioned tunneling (some
  admins run legitimate tunnels — know about them before hunting).

## Procedure

1. **Start with DNS — the highest-signal, cheapest telemetry.** Hunt: high query volumes to rare or newly observed domains, long/random subdomains (tunneling), TXT/NULL record abuse, queries for newly registered domains, and beacon-regular query timing. Aggregate by source host and rank by anomaly score, not raw volume — your DCs will always out-query everything.
2. **Analyze HTTP(S) sessions for beaconing.** Extract session inter-arrival times per (host, destination) pair. Machine-regular callbacks with jitter stand out statistically against human browsing. Flag: long-lived sessions with tiny, regular payloads; identical user-agents across unrelated hosts; POST-heavy ratios to destinations with no legitimate upload function; regular callbacks to cloud/SaaS hosts the organization doesn't use.
3. **Inspect for tunneling and covert channels.** Look for DNS/ICMP/HTTP carrying non-protocol payloads: oversized DNS queries, ICMP with data payloads beyond normal ping sizes, HTTP to bare IPs with no hostname (or Host headers mismatching the TLS SNI), and WebSocket connections with unusual longevity. Decode one session manually before writing a signature — understand the encoding first, or your signature will miss the variant.
4. **Fingerprint the TLS layer.** Compare JA3/JA4 fingerprints of suspect sessions against known-good clients for the claimed application. Mismatches (e.g., a "browser" user-agent with a non-browser TLS stack) are strong, tool-agnostic indicators that survive many C2 customizations. Maintain a fingerprint allowlist for your sanctioned applications.
5. **Characterize the channel fully.** For each confirmed C2 document: protocol, encoding/encryption observed, callback interval and jitter, tasking vs. exfiltration direction and ratio, fallback channels configured, and infrastructure behind it. This characterization drives both the block strategy and the detection logic — and tells responders what the adversary could have done (tasking received = assume commands were executed).
6. **Map the infrastructure.** Pivot on IPs, domains, certificates, and ASNs: passive DNS, WHOIS history, and certificate transparency reveal related infrastructure. Distinguish dedicated attacker infrastructure from compromised legitimate hosts and shared cloud/CDN fronting — your block strategy differs fundamentally for each (block vs. remediate vs. surgical hostname block).
7. **Determine data impact.** Quantify bytes transferred per direction per host over the channel's lifetime. Sustained outbound volume after initial compromise suggests staging/exfiltration — escalate to data-impact scoping with the data owners and legal. Inbound-heavy channels suggest tooling delivery — hunt for what was dropped.
8. **Disrupt carefully and deliberately.** Coordinate blocks (DNS firewall/RPZ, proxy rules, EDR network quarantine, firewall rules) with the incident commander: blocking too early tips off the adversary before you've scoped the intrusion; blocking too late extends exfiltration. Prefer silent sinkholing for intelligence collection, hard blocks for containment — decide explicitly, don't drift into one.
9. **Convert to durable detections.** Deploy: DNS-tunneling analytics, beaconing detection on NetFlow/Zeek logs, JA3/JA4 mismatch rules, proxy rules for the characterized URIs/headers, and EDR network-event rules for the endpoint side. Tune against baseline to keep false positives manageable, and document what each detection catches.
10. **Verify the kill.**
    After containment, monitor for fallback channels (the adversary's Plan
    B): new DNS patterns from the same hosts, new destinations with similar
    timing characteristics, traffic spikes on previously quiet protocols,
    and DoH/DoT usage appearing where it wasn't.
    C2 disruption is confirmed by sustained silence across all layers, not
    by a single block rule.

## Key tools & commands

- Zeek (Bro) — protocol logs (dns.log, http.log, ssl.log, conn.log) ideal
  for C2 hunting at scale; the foundation most analytics build on.
- RITA or equivalent beaconing/tunneling analytics — statistical detection
  of periodic callbacks and long connections over Zeek logs.
- Wireshark/tshark — manual session decoding and verification:
  `tshark -r c2.pcap -Y dns -T fields -e dns.qry.name -e dns.txt`.
- JA3/JA4 fingerprinting via Zeek/Suricata — TLS client anomaly detection
  independent of payload visibility.
- Passive DNS, WHOIS history, certificate transparency — infrastructure
  pivoting.
- Full-packet capture (Security Onion, Arkime/Moloch, or appliance PCAP) —
  for the manual decode step and evidence preservation.

## Expected outputs

- Characterized C2 channels: protocol, encoding, timing, infrastructure,
  per-host timelines with first/last seen.
- Infrastructure map distinguishing attacker-owned, compromised-legitimate,
  and shared-fronting assets, with block recommendations per category.
- Data-impact estimate: bytes per direction per host over channel lifetime,
  handed to legal/data owners.
- Deployed layered detections (DNS analytics, beaconing, JA3/JA4,
  proxy/IDS, EDR) with tuning notes.
- Verified disruption: post-block monitoring results showing sustained
  silence or catching fallback attempts.

## Pitfalls

- Encrypted C2 without TLS interception limits you to metadata — be honest
  about what you cannot see, and lean on timing, sizing, and endpoint
  telemetry instead of guessing at payloads.
- Blocking a CDN-fronted C2 by IP takes down legitimate services sharing the
  front; use DNS/proxy-layer blocks on the specific hostname instead.
- Legitimate software beacons constantly (updaters, telemetry, sync
  clients, monitoring agents). Baseline first or every detection becomes a
  false positive that trains the SOC to ignore the rule.
- Declaring victory after one block: modern implants have fallback
  channels, DGAs, and dead-drop resolvers. Monitor for the adversary's next
  move; don't assume there isn't one.
- Sampling in NetFlow hides low-volume C2: know your sampling rate and
  supplement with DNS/proxy logs that are unsampled.

## References

- MITRE ATT&CK: T1071 (Application Layer Protocol), T1048 (Exfiltration
  Over Alternative Protocol), T1572 (Protocol Tunneling), T1008 (Fallback
  Channels), T1132 (Data Encoding), T1071.004 (DNS)
- Zeek documentation (protocol log formats for hunting: dns.log, conn.log,
  ssl.log)
- JA3/JA4 fingerprinting references
- SANS / community C2-analysis write-ups (beaconing statistics methodology)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
