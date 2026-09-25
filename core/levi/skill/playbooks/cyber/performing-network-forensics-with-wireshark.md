---
skill_id: cyber_performing_network_forensics_with_wireshark
name: Network Forensics with Wireshark
description: Investigate packet captures in Wireshark to reconstruct attacker activity, extract files, and build evidentiary timelines.
risk: low
permissions: []
requires_confirmation: false
tags: [network, forensics, wireshark]
version: 1.0.0
---

## Purpose
- Turn raw packet captures into a clear narrative of what happened on the wire during an incident.
- Extract transferred files, credentials in cleartext protocols, and C2 sessions as evidence.
- Validate or refute hypotheses from logs and endpoint alerts with ground-truth packet data.
- Give non-network specialists a guided path through the most probative parts of a capture.

## When to use
- When an incident includes full or partial packet captures from taps, SPAN ports, or endpoint sensors.
- When investigating suspected data exfiltration, lateral movement, or command-and-control traffic.
- When logs are incomplete or untrusted and packet evidence is needed to establish facts.
- When validating IDS or NDR alerts with independent packet-level review.

## Prerequisites
- The capture files with documented provenance, time synchronization details, and any decryption keys for authorized TLS inspection.
- Wireshark installed on an analysis workstation with enough memory for the capture size.
- Context from the incident: suspect IPs, time windows, and the assets involved.
- Adequate storage for extracted objects and exported evidence.

## Procedure
1. Verify capture integrity with hashes, confirm the capture time zone and clock accuracy, and note any gaps or truncation.
2. Build an initial profile: protocol hierarchy, top talkers, and conversation statistics to spot unusual volume or protocols.
3. Filter to the incident time window and suspect endpoints, then follow TCP and UDP streams to reconstruct sessions.
4. Hunt for beaconing patterns, DNS tunneling, oversized ICMP or DNS payloads, and cleartext credential exchanges.
5. Extract transferred files and objects from HTTP, SMB, FTP, and TFTP streams, hashing each for threat-intel lookup.
6. Reassemble fragmented or obfuscated sessions and document attacker commands visible in cleartext or decrypted traffic.
7. Analyze encrypted sessions through metadata: certificate details, JA3 fingerprints, flow sizes, and timing patterns.
8. Correlate findings with firewall, proxy, and endpoint logs to build a single timeline of the intrusion.
9. Export key packets, IO graphs, and extracted files into the case evidence store with analyst notes.
10. Summarize the packet-level narrative for the incident report, separating confirmed facts from analyst inference.

## Expected outputs
- A packet-level incident narrative with timelines, session reconstructions, and extracted artifacts.
- IOCs including IPs, domains, URLs, and file hashes derived directly from observed traffic.
- Evidence exports suitable for legal or management reporting.
- A clear statement of capture limitations and what the packets could not show.

## Pitfalls
- Misreading timestamps when the capture host clock was wrong; always validate against a known event.
- Assuming encrypted traffic is benign; analyze metadata, JA3 fingerprints, and flow behavior even when payloads are opaque.
- Overlooking capture gaps from SPAN oversubscription, which can hide the most important packets.
- Presenting analyst inference as fact; label reconstructions as reconstructions.

## References
- Wireshark documentation, https://www.wireshark.org/docs/
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR572 network forensics course materials
- Wireshark display filter reference, https://www.wireshark.org/docs/dfref/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
