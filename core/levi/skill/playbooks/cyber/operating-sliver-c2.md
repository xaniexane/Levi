---
skill_id: cyber_operating_sliver_c2
name: Detecting Sliver C2 Infrastructure (Defensive)
description: Detect and dismantle Sliver command-and-control infrastructure in your environment.
risk: low
permissions: []
requires_confirmation: false
tags: [c2-detection, threat-hunting, incident-response]
version: 1.0.0
---
## Purpose
Sliver is an open-source C2 framework widely abused by threat actors. This is strictly a defensive playbook: recognizing Sliver's implant and network characteristics, hunting for them, and responding effectively. It contains no instructions for deploying or operating C2 infrastructure.

## When to use
- Threat intel links Sliver to actors targeting your sector.
- Hunting for implants during incident response or proactive threat hunting.
- Validating that your detections catch common open-source C2 frameworks.

## Prerequisites
- EDR with process-tree, network, and memory visibility across the fleet.
- Network logs with TLS metadata and DNS query data.
- Defender-published research on Sliver implant characteristics and infrastructure patterns.

## Procedure
1. **Know the implant profile.** Sliver implants (sessions/beacons) support multiple transports (HTTPS, DNS, mTLS, WireGuard); study published defender analysis for default configurations, staging patterns, and known infrastructure.
2. **Hunt beaconing behavior.** Look for regular-interval callbacks to external infrastructure, mTLS sessions from non-browser processes, and DNS tunneling patterns on endpoints that should not exhibit them.
3. **Examine process anomalies.** Flag unsigned binaries with network egress, processes injecting into legitimate ones, and implants running from unusual paths (temp directories, user profiles).
4. **Check persistence and staging.** Review scheduled tasks, services, registry run keys, and recent downloads on suspect hosts; Sliver operators commonly stage via scripts or droppers first.
5. **Scope before acting.** Map every compromised host and the initial access vector; coordinate containment so the operator does not realize they are discovered mid-investigation.
6. **Contain and eradicate.** Block infrastructure at all egress controls, isolate hosts, remove persistence, capture forensic images of key hosts, and rotate exposed credentials.
7. **Convert to detection.** Write SIEM/EDR detections for the observed TTPs (not just hashes), share IOCs with your community, and remediate the entry point.

8. **Watch for re-compromise.** After eradication, monitor the same hosts and entry vectors for 30 days; operators often return through the same gap.
9. **Brief leadership factually.** Report what was confirmed, what was ruled out, and what remains unknown — speculation in executive briefings becomes organizational mythology.

## Expected outputs
- Hunt package: queries for Sliver-like beaconing and implant behavior.
- Incident scope with eradication and credential-rotation records.
- TTP-based detections added to the detection catalog.
- Example: mTLS sessions from a non-browser process on a server, beaconing every 5 minutes to external infrastructure, lead to a Sliver implant; the staging script in a temp directory reveals the initial access vector.

## Pitfalls
- Hash-only detection: Sliver implants are trivially recompiled, so hunt behaviors.
- Alerting the operator with premature blocking before the intrusion is scoped.
- Forgetting the staging chain: removing the implant but leaving the dropper's persistence.

- Assuming the implant is the whole intrusion; Sliver is often stage two, so hunt for the initial access and staging chain with equal effort.
- Neglecting DNS and mTLS transports while hunting only HTTPS; check every transport the framework supports.

## References
- MITRE ATT&CK T1071 (Application Layer Protocol), T1059 (Command and Scripting Interpreter).
- CISA incident response guidance (cisa.gov).
- SANS FOR508 (sans.org) — hunting for C2 and persistence.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
