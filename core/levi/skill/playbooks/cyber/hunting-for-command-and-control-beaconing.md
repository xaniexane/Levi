---
skill_id: cyber_hunting_for_command_and_control_beaconing
name: Hunting for Command-and-Control Beaconing
description: A general C2 beaconing hunt framework: combining timing analysis, protocol anomalies, and endpoint correlation across implant families.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, network, c2]
version: 1.0.0
---
## Purpose

This is the general-purpose C2 beaconing hunt playbook: the framework for
finding command-and-control check-ins regardless of implant family. It
combines timing analysis, protocol and payload anomalies, DNS-based C2
indicators, and endpoint correlation into one repeatable workflow that
complements the family-specific (Cobalt Strike) and technique-specific
(frequency analysis, DNS tunneling, domain fronting) hunts.

## When to use

- As the standing network-hunting program: run on a recurring cadence.
- After an initial compromise is found: hunt for additional C2 channels
  the first implant may have opened.
- When a new implant family appears in threat intel: adapt the framework
  with family-specific indicators.
- To validate egress monitoring coverage before an adversary does.

## Prerequisites

- 30+ days of network telemetry: proxy, firewall, DNS, NetFlow/Zeek.
- Endpoint telemetry for attribution (which process made the
  connection).
- Threat intel on C2 techniques relevant to your sector.
- Baselines of legitimate automated traffic (updaters, sync, telemetry).

## Procedure

1. **Start with the long-tail of destinations.** Rank external
   destinations by rarity across the fleet and by age/reputation.
   C2 infrastructure is typically rare (few hosts contact it) and young
   (recently registered) — the intersection is your initial candidate
   set.
2. **Apply timing analysis.** For each candidate destination, compute
   connection periodicity per source host (see the frequency-analysis
   playbook). Persistent, regular check-ins from a host to a rare
   destination are the core beaconing signal.
3. **Inspect protocol usage.** Flag: HTTP(S) to IPs without hostnames,
   non-standard ports for the protocol, TLS with unusual fingerprints
   or self-signed certificates, DNS query patterns inconsistent with
   normal resolution (high entropy, excessive TXT queries), and
   protocols tunneled over unexpected ports.
4. **Examine payload symmetry and size.** C2 check-ins are often small
   and symmetric (heartbeat out, tasking in), with occasional large
   bursts (exfiltration or tooling download). Flag connections whose
   size profile deviates from the destination's normal pattern.
5. **Check for C2-adjacent DNS behaviors.** Include fast-flux indicators
   (rapidly changing A records, very low TTLs), domain-generation-
   algorithm patterns (high-entropy, unpronounceable names, NXDOMAIN
   bursts), and DNS over unexpected channels.
6. **Attribute to processes.** For surviving candidates, pull endpoint
   data: the connecting process, its parent chain, signature status,
   and start time. Legitimate software explains itself; implants hide
   in unusual parents, unsigned binaries, or injected processes.
7. **Confirm persistence and scope.** Verify the beaconing persists
   across days and reboots, then scope: which hosts, which users, what
   the implant did between check-ins (credential access, lateral
   movement, staging). Build the incident timeline.
8. **Respond and institutionalize.** Block confirmed C2 at egress (with
   change control), isolate affected hosts via IR, extract IOCs for
   sharing, and convert the successful hunt logic into a scheduled
   analytic with measured precision.

## Expected outputs

- Ranked C2 candidates with timing, protocol, and reputation analysis.
- Confirmed findings with endpoint attribution and timelines.
- Blocked infrastructure and incident-response handoffs.
- A recurring C2-hunting analytic with tuning history.

## Pitfalls

- Rarity alone is not malicious — new SaaS tools and marketing pixels
  are rare too; require timing or protocol anomalies before escalating.
- Encrypted C2 hides payload but not timing, size, or destination —
   do not declare "nothing to find" on encrypted traffic.
- Proxy and NAT aggregation distort per-host timing — get as close to
   the endpoint as telemetry allows.
- One-off hunts decay — beaconing analytics need recurring execution
   and threshold maintenance.
- Blocking C2 before scoping is complete can tip off the adversary —
   coordinate timing with incident response.

## References

- MITRE ATT&CK: T1071 (Application Layer Protocol), T1572
  (Protocol Tunneling), T1568 (Dynamic Resolution)
- NIST SP 800-94: Guide to Intrusion Detection and Prevention Systems
- CISA: C2-related advisories and hunting guidance
- Zeek and proxy-log documentation for field references
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
