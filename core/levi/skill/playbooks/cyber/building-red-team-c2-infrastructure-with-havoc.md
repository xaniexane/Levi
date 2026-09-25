---
skill_id: cyber_building_red_team_c2_infrastructure_with_havoc
name: Detecting Havoc Framework Command-and-Control Usage
description: Blue-team playbook for identifying and disrupting command-and-control activity associated with the Havoc adversary-emulation framework.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, threat-intel, network]
version: 1.0.0
---
## Purpose
Havoc is an open-source adversary-emulation framework used by legitimate red teams and, increasingly, by threat actors. Defenders need to recognize its artifacts regardless of who deployed it. This playbook covers detecting Havoc implants and listeners -- network signatures, endpoint artifacts, and infrastructure patterns -- and responding appropriately. It contains no guidance on deploying or operating the framework.

## When to use
- Hunting for C2 frameworks beyond the usual commercial tooling.
- Investigating alerts involving unusual HTTPS beaconing or custom implants.
- Validating that an authorized engagement's Havoc usage stayed within scope.
- Building detections after Havoc appears in threat-intelligence reporting.

## Prerequisites
- Network telemetry (TLS metadata, flow records) and endpoint telemetry (EDR/Sysmon).
- Open-source detection references describing Havoc's default profiles and artifacts.
- Record of authorized engagements and their approved tooling and time windows.
- Containment capability: host isolation and egress blocking.

## Procedure
1. Inventory known artifacts. Collect Havoc's default listener profiles, default ports, certificate patterns, and implant behaviors from reputable detection research.
2. Hunt network beacons. Look for HTTPS sessions with periodic timing, distinctive JA3 hashes, and malleable-profile HTTP characteristics that match the framework's defaults.
3. Examine endpoint artifacts. Correlate beaconing processes with process-creation events, service or task persistence, and unsigned binaries in unusual paths.
4. Check for customization. Note that operators change default profiles; pivot on behavior (beaconing, injection patterns) rather than defaults alone.
5. Scope the activity. Determine affected hosts, duration, and data accessed; reconcile timestamps against authorized engagement windows.
6. Contain and eradicate. Isolate hosts, block listener infrastructure, remove persistence mechanisms, and reset credentials on impacted systems.
7. Write durable detections. Encode behavior-based rules (beaconing cadence, TLS fingerprints, process anomalies) rather than only default indicators.
8. Share findings. Report unauthorized usage through your threat-intel channels; brief the red team on detections if the use was authorized.

## Expected outputs
- Detection rules for Havoc network and endpoint artifacts.
- Scoped incident findings with authorized-versus-unauthorized determination.
- Hardening recommendations to block the observed techniques.

## Pitfalls
- Defaults-only detections miss operators who customize profiles; anchor on behavior.
- Legitimate red-team traffic misclassified as intrusion wastes incident-response effort.
- Blocking a single listener IP rarely ends the campaign; expect profile rotation.
- Overly aggressive TLS fingerprinting can false-positive on legitimate applications.

## References
- MITRE ATT&CK: TA0011 (Command and Control), T1071 (Application Layer Protocol)
- MITRE ATT&CK: T1055 (Process Injection), T1543 (Create or Modify System Process)
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
