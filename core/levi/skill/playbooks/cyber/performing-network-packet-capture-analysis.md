---
skill_id: cyber_performing_network_packet_capture_analysis
name: Network Packet Capture Analysis
description: Apply a structured, tool-agnostic workflow to validate, profile, and investigate packet captures during incidents.
risk: low
permissions: []
requires_confirmation: false
tags: [network, forensics, pcap]
version: 1.0.0
---

## Purpose
- Provide a repeatable capture-analysis workflow that works regardless of which tool captured or opens the file.
- Catch capture-quality problems early so analysts do not draw conclusions from truncated or lossy data.
- Standardize how the team profiles traffic, hunts anomalies, and documents findings.
- Make capture analysis teachable so junior analysts produce consistent, reviewable work.

## When to use
- Whenever a packet capture arrives as incident evidence, from any source or capture tool.
- When triaging multiple captures from different sensors that must be compared consistently.
- When training analysts on a vendor-neutral approach before they specialize in a particular tool.
- When handing captures between teams or to external responders who use different tooling.

## Prerequisites
- Capture files with provenance records and, where relevant, the capture filter and interface details used.
- At least one analysis tool (Wireshark, tshark, Zeek, or Suricata) and a machine able to handle the capture size.
- Incident context: assets of interest, time windows, and the questions the capture is expected to answer.
- A case tracking system where findings, hashes, and limitations are recorded.

## Procedure
1. Record provenance and hash each capture, then check for truncation, snaplen limits, and packet loss indicators.
2. Determine the capture scope: which segment was tapped, what filter was applied, and what traffic is therefore invisible.
3. Profile the capture statistically: duration, packet and byte counts, protocol mix, and top conversations.
4. Establish what normal looks like for the captured segment using baselines or comparable quiet periods.
5. Narrow to the incident window and involved hosts, then characterize normal traffic so anomalies stand out.
6. Hunt systematically for exfiltration signals, C2 beacons, tunneling, scanning, and lateral movement patterns.
7. Extract files, certificates, and session payloads relevant to the investigation, hashing everything extracted.
8. Build a timeline of attacker-visible events and cross-check it against host and application logs.
9. Document limitations explicitly, including blind spots from filters, encryption, or capture loss, in the final report.
10. Peer-review the analysis before findings go into the incident record or legal hold.

## Expected outputs
- A validated capture inventory with quality notes and scope limitations.
- An anomaly register with supporting packet evidence for each finding.
- A correlated timeline and extracted artifacts ready for the case file.
- A peer-reviewed analysis summary suitable for stakeholders.

## Pitfalls
- Drawing conclusions from a capture without knowing the capture filter; filtered-out traffic is a built-in blind spot.
- Ignoring snaplen truncation, which silently removes the payloads analysts most want to see.
- Treating one sensor's view as the whole network; always ask what the capture could not see.
- Skipping peer review on high-stakes findings such as alleged data exfiltration.

## References
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- Wireshark documentation, https://www.wireshark.org/docs/
- Zeek documentation on log-based traffic analysis, https://docs.zeek.org/
- RFC 793 and related protocol specifications for ground-truth behavior
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
