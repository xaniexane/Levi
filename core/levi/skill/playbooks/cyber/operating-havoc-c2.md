---
skill_id: cyber_operating_havoc_c2
name: Detecting Havoc C2 Infrastructure (Defensive)
description: Detect and dismantle Havoc command-and-control infrastructure in your environment.
risk: low
permissions: []
requires_confirmation: false
tags: [c2-detection, threat-hunting, incident-response]
version: 1.0.0
---
## Purpose
Havoc is an open-source command-and-control framework abused by threat actors. This is strictly a defensive playbook: recognizing Havoc's network and host indicators, hunting for its presence, and responding when found. It contains no instructions for deploying or operating C2 infrastructure.

## When to use
- Threat intel indicates Havoc use by actors targeting your sector.
- Hunting for C2 beacons during or after a suspected intrusion.
- An EDR or network alert suggests unknown C2-like beaconing.

## Prerequisites
- Network telemetry: firewall/proxy logs, DNS logs, and ideally TLS fingerprinting (JA3/JA4).
- EDR with process, network-connection, and in-memory visibility.
- Current threat intel on Havoc indicators (listener profiles, default configurations, known infrastructure).

## Procedure
1. **Know the profile.** Havoc agents (Demons) beacon to teamserver listeners over HTTP/HTTPS, SMB, or other transports; study published defender research for default URIs, headers, jitter, and certificate characteristics.
2. **Hunt network beacons.** Look for periodic, low-jitter HTTPS connections to rare external hosts, unusual user-agents, and long-lived sessions from servers or workstations that should not browse.
3. **Inspect TLS fingerprints.** Compare JA3/JA4 hashes of suspicious flows against known Havoc-associated fingerprints from intel sharing communities.
4. **Examine hosts.** Check EDR for unsigned or newly-dropped binaries making outbound connections, in-memory-only payloads, and persistence via services or scheduled tasks tied to the beaconing process.
5. **Scope the intrusion.** Identify patient zero, the initial access vector, and every host the implant touched; assume credential exposure on compromised hosts.
6. **Contain and eradicate.** Block C2 infrastructure at proxy/firewall/DNS, isolate hosts, kill persistence, and rotate credentials; do not tip off the operator before scoping is complete.
7. **Share and harden.** Report IOCs to your ISAC, add detections to the SIEM, and close the initial-access gap that let the implant in.

8. **Hunt for related tooling.** Operators rarely deploy one tool; hunt concurrently for credential dumpers, lateral-movement utilities, and persistence mechanisms from the same timeframe.
9. **Update the threat model.** Feed confirmed Havoc TTPs into detection engineering and threat modeling so the next similar framework is caught by behavior, not by name.

## Expected outputs
- Hunt queries for Havoc-like beaconing across network and endpoint data.
- Scoped incident record with containment actions and IOC sharing.
- New SIEM detections for the observed C2 patterns.
- Example: periodic HTTPS beacons with 60-second jitter to a rare external host, combined with an unsigned binary in a user profile, confirm a Havoc implant; scoping finds 3 hosts before containment.

## Pitfalls
- Blocking the C2 domain before scoping: the operator goes quiet and you lose visibility.
- Relying on a single indicator (e.g., one JA3 hash) that the operator can change trivially.
- Declaring victory at host isolation without finding the initial access vector.

- Hunting only for default configurations; operators customize listener profiles, so hunt the behavioral class (periodic beaconing, rare infrastructure), not the defaults.
- Sharing IOCs without TLP markings, causing partners to either over-share or under-use the intelligence.

## References
- MITRE ATT&CK T1071 (Application Layer Protocol) — C2 techniques.
- CISA guidance on C2 detection and incident response (cisa.gov).
- MITRE D3FEND (d3fend.mitre.org) — network traffic analysis countermeasures.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
