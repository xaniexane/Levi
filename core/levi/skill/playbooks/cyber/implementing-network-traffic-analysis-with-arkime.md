---
skill_id: cyber_implementing_network_traffic_analysis_with_arkime
name: Implementing Network Traffic Analysis with Arkime
description: Deploy Arkime (formerly Moloch) for full-packet capture and indexed traffic analysis — capture architecture, retention, and hunt workflows.
risk: info
permissions: []
requires_confirmation: false
tags: [network, forensics, packet-capture, arkime]
version: 1.0.0
---
## Purpose

Give analysts the ability to answer "what actually crossed the wire" — full packets, indexed and searchable. Arkime captures traffic at scale, indexes session metadata in Elasticsearch/OpenSearch, and stores pcaps for retrieval, turning network forensics from a theoretical capability into a routine one: investigate the alert, pivot to the session, read the packets.

## When to use

- Building network forensics capability for incident response (retrospective analysis of what happened before the alert).
- Hunting for C2, data exfiltration, and lateral movement with session-level evidence.
- Validating IDS/IPS alerts against ground-truth packet data.
- Meeting requirements for network traffic retention in regulated environments.
- Replacing ad-hoc tcpdump captures with always-on, indexed capture.

## Prerequisites

- Capture points planned: SPAN ports, taps, or cloud packet mirroring at key choke points (internet edge, DMZ, data-center core, OT conduits).
- Storage sizing: full-packet capture is storage-hungry — calculate from actual throughput × retention target, with compression expectations documented. This is the budget line that kills projects; size it first.
- Elasticsearch/OpenSearch cluster for the session index, sized for session counts (not just bytes).
- Legal/privacy review: full-packet capture records content, including credentials and personal data — define access controls, retention, and handling before capturing.
- Time synchronization across sensors (microsecond-level matters for session correlation).

## Procedure

1. **Design the capture architecture.** Deploy Arkime capture nodes at each tap/SPAN point, with viewer and Elasticsearch centrally. Dedicate capture NICs (no IP, promiscuous mode) and separate management interfaces. For encrypted or high-throughput links, plan TLS considerations and packet-slicing policies (capture full packets for forensics value; slice only if storage math forces it, and document what is lost).
2. **Tune capture for zero loss.** Configure worker threads, ring buffers, and PF_RING or DPDK capture paths appropriate to the link speed. Monitor capture loss relentlessly — a sensor dropping packets under load produces incomplete sessions that mislead investigations. Benchmark at peak throughput, not average.
3. **Build the session index.** Let Arkime index sessions into Elasticsearch with enriched fields: GeoIP, ASN, protocol parsers (HTTP, DNS, TLS certificates, SMB), and file extraction where configured. Create index lifecycle policies matching the retention target; sessions age out, pcaps age out on their own schedule.
4. **Integrate threat intelligence.** Feed Arkime with intel feeds (threat intel plugin or WiseService): tag sessions touching known-malicious IPs, domains, JA3 hashes, and certificates. Intel-tagged sessions become pivot points during hunts and triage.
5. **Define the hunt and IR workflows.** Document the standard pivots: from an alert (IP/domain/hash) to sessions to packets; from a compromised host to all its sessions in the dwell window; from a suspicious JA3 to every host using it. Train analysts on Arkime's query language and SPI graphs before the incident, not during.
6. **Control access tightly.** Full-packet capture is among the most sensitive data stores in the organization. Restrict Arkime access to IR and hunt roles, log every query (analysts' searches are themselves auditable), and encrypt pcap storage at rest. Define who may export pcaps and under what authorization.
7. **Plan retention and legal hold.** Implement the retention schedule (e.g., 30 days full packets, 90 days session metadata — adjust to threat model and regulation), with legal-hold capability to preserve data beyond retention for active investigations. Automate expiry; manual deletion does not scale and invites inconsistency.
8. **Exercise the capability.** Run quarterly hunts using Arkime as the primary data source (e.g., "find all hosts with beacon-like DNS patterns in the last 30 days") and include packet-level evidence in IR tabletop exercises. Unused capture infrastructure atrophies — analysts default to what they know.

## Expected outputs

- Capture architecture with sensors at defined choke points, tuned for zero packet loss.
- Indexed session store with enrichment and intel tagging.
- Documented hunt/IR workflows using Arkime pivots.
- Access controls, query audit logging, and encrypted pcap storage.
- Retention and legal-hold procedures; quarterly hunt exercises.

## Pitfalls

- **Undersized storage.** Capture projects die when disks fill in week one and retention collapses to days. Size from measured peak throughput with headroom, and monitor fill rates with alerts.
- **Packet loss ignored.** A sensor dropping 10% of packets still "works" — it just produces wrong conclusions. Treat any sustained capture loss as a P1 for the forensics capability.
- **No privacy/access controls.** Full packets contain passwords, PII, and business secrets. Broad analyst access without query auditing creates insider-risk and compliance exposure.
- **TLS blindness unacknowledged.** Most traffic is encrypted; Arkime sees metadata, not content, for TLS sessions. Pair with endpoint telemetry and TLS fingerprinting rather than pretending packets reveal everything.
- **Capture without analysts.** Terabytes of indexed packets nobody queries is expensive noise. The capability requires trained hunters with time allocated — budget the people with the hardware.

## References

- Arkime documentation — https://arkime.com/
- NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident Response" — https://csrc.nist.gov/publications/detail/sp/800-86/final
- MITRE ATT&CK T1040 (Network Sniffing — defensive application) and T1071 (Application Layer Protocol) — https://attack.mitre.org/
- SANS network forensics guidance (process and methodology references)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
