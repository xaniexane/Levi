---
skill_id: cyber_detecting_arp_poisoning_in_network_traffic
name: Detecting ARP Poisoning in Network Traffic
description: Detect ARP spoofing and man-in-the-middle attempts with traffic analysis, static defenses, and switch features.
risk: info
permissions: []
requires_confirmation: false
tags: [network, detection, mitm]
version: 1.0.0
---
## Purpose

Detect ARP poisoning — attackers corrupting ARP caches to intercept traffic — using network monitoring, switch-level protections, and host-based checks. ARP has no authentication by design, so detection and prevention must come from the layers around it.

## When to use

- Investigating suspected man-in-the-middle activity on a LAN segment.
- Hardening switched networks against internal eavesdropping and session hijacking.
- Validating that dynamic ARP inspection (DAI) is actually working.
- Post-incident forensics where credential theft suggests local interception.

## Prerequisites

- SPAN/tap visibility into the LAN segment or an NIDS (Snort/Suricata/Zeek) with ARP analysis enabled.
- Managed switches capable of dynamic ARP inspection and DHCP snooping.
- Baseline of normal ARP behavior: gateway MACs, gratuitous ARP sources, static entries.
- Host inventory for deploying ARP-monitoring agents where switches can't help (unmanaged segments).

## Procedure

1. **Monitor ARP traffic for poisoning signatures.** With Zeek, Suricata, or Wireshark, alert on: gratuitous ARP replies (opcode 2) not preceded by requests, rapid ARP reply storms, MAC address flapping (same IP claimed by different MACs in short windows), and ARP replies claiming the gateway's IP from an unexpected MAC. These are the canonical poisoning indicators.
2. **Enable DHCP snooping and dynamic ARP inspection on switches.** Configure DHCP snooping to build the trusted IP-MAC binding table, then enable DAI to drop ARP packets that don't match bindings. This is the strongest preventive control — verify it's actually dropping with a controlled test from an authorized host before relying on it.
3. **Deploy static ARP entries for critical hosts.** On servers and gateways, set static ARP entries for the default gateway and critical peers. Static entries can't be poisoned — use them where the administrative overhead is manageable (servers, not the whole DHCP fleet).
4. **Watch for the attacker's follow-on behavior.** ARP poisoning is a means, not an end. Correlate ARP anomalies with: new packet-forwarding on the suspect host (IP forwarding enabled), SSL-stripping or credential-harvesting indicators, DNS anomalies from the same host, and lateral-movement alerts. The poisoning alert plus credential theft is the incident.
5. **Use host-based detection where network controls are blind.** On unmanaged segments or critical hosts, run arpwatch or OSQuery ARP-table monitoring to alert on gateway MAC changes. A host whose gateway MAC changes unexpectedly is either under attack or misconfigured — both deserve investigation.
6. **Respond by isolating the poisoning host.** On confirmed poisoning: identify the spoofing MAC, trace it to a switch port, shut down or quarantine the port, and capture the host for forensics. Clear ARP caches on affected hosts (or let entries age out) and verify the gateway MAC is correct everywhere before declaring the segment clean.

## Expected outputs

- NIDS/Zeek ARP-poisoning detections with alerting on gratuitous replies, MAC flapping, and gateway impersonation.
- DHCP snooping + DAI enabled and tested on managed switches; static ARP on critical hosts.
- A port-quarantine response procedure for confirmed poisoning sources.

## Pitfalls

- DAI without DHCP snooping — DAI has no binding table to validate against and does nothing.
- Trusting DAI on trunks without configuring trusted ports — legitimate ARP gets dropped and you "fix" it by disabling DAI.
- Alerting on every gratuitous ARP — some are legitimate (HA failover, IP conflict detection); baseline first.
- Forgetting wireless — ARP poisoning works on Wi-Fi too; extend monitoring to wireless segments.
- Clearing the victim's ARP cache but not finding the poisoner — the attack resumes immediately.

## References

- MITRE ATT&CK T1557.002 (Adversary-in-the-Middle: ARP Cache Poisoning)
- Cisco / switch-vendor documentation on DHCP snooping and dynamic ARP inspection
- Zeek documentation — ARP analysis scripts
- NIST SP 800-94 (Guide to Intrusion Detection and Prevention Systems)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
