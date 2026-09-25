---
skill_id: cyber_performing_packet_injection_attack
name: Packet Injection Detection and Analysis
description: Detect, analyze, and attribute malicious packet injection on the network from a defensive standpoint.
risk: low
permissions: []
requires_confirmation: false
tags: [network, detection, forensics]
version: 1.0.0
---

## Purpose
- This playbook addresses packet injection strictly from the defender's side: detecting injected packets, analyzing them, and hardening the network. It does not provide instructions for injecting packets into networks you do not own.
- Teach analysts to recognize injected packets: RST injection, DNS spoofing, ARP spoofing, and session hijack attempts.
- Distinguish malicious injection from benign causes such as misconfigured middleboxes or asymmetric routing.
- Build detections and hardening controls that make injection harder and more visible.

## When to use
- When users report connections being reset or redirected in ways that suggest on-path interference.
- When DNS answers or ARP tables contain entries that do not match authoritative sources.
- When threat intelligence warns of ISP-level or adversary-in-the-middle injection campaigns.
- When validating that network controls actually prevent common injection techniques.

## Prerequisites
- Packet capture capability at relevant network points and baseline knowledge of normal traffic.
- Access to authoritative DNS and ARP reference data for comparison.
- An authorized test environment if active validation of defenses is required.
- Coordination with network operations so defensive testing does not trigger incident response.

## Procedure
1. Define the suspected injection type from symptoms: unexpected RSTs, DNS mismatches, ARP anomalies, or session anomalies.
2. Capture traffic at multiple vantage points to compare what the client saw against what the server sent.
3. Analyze TCP RST packets: check sequence numbers, TTL values, and timing against the legitimate session to spot forgery.
4. Compare DNS responses against authoritative answers; flag mismatched IPs, abnormal TTLs, and responses arriving impossibly fast.
5. Inspect ARP tables and gratuitous ARP traffic for spoofing, correlating claimed MAC addresses with switch port data.
6. Look for TTL and IP ID anomalies that suggest packets were crafted rather than forwarded by the real endpoint.
7. Rule out benign causes: load balancers, security appliances, and misconfigured NAT can all mimic injection.
8. If injection is confirmed, scope the affected segments and preserve captures as evidence with hashes.
9. Harden: enforce DNSSEC validation, deploy dynamic ARP inspection and DHCP snooping, and prefer encrypted protocols that resist injection.
10. Create detections for the observed injection signatures so recurrence triggers alerts.
11. Deploy longer-term passive monitoring on affected segments to catch intermittent injection campaigns.
12. Share sanitized indicators with peer organizations and sector ISACs when injection is confirmed.

## Expected outputs
- A confirmed or ruled-out determination with packet evidence for the injection hypothesis.
- Characterization of the injection technique observed, with indicators for detection.
- Hardening recommendations and new detection rules.

## Pitfalls
- Declaring injection from a single vantage point; middleboxes legitimately alter packets in transit.
- Confusing retransmissions and out-of-order delivery with crafted packets.
- Attempting active counter-injection or retaliation, which is both ineffective and legally hazardous.
- Blaming injection for what is actually a failing NIC or duplex mismatch; rule out hardware first.

## References
- CAIDA research on internet-scale packet injection observations
- MITRE ATT&CK adversary-in-the-middle techniques, https://attack.mitre.org/tactics/TA0005/
- IETF RFCs on TCP (RFC 793) and ARP (RFC 826) for protocol ground truth
- NIST SP 800-94 Guide to Intrusion Detection and Prevention Systems
- Vendor documentation on dynamic ARP inspection and DHCP snooping
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
