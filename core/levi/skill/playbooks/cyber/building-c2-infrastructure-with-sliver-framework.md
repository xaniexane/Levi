---
skill_id: cyber_building_c2_infrastructure_with_sliver_framework
name: Detecting Sliver Framework Command-and-Control Infrastructure
description: Blue-team playbook for identifying, analyzing, and disrupting Sliver-framework-based command-and-control infrastructure.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, threat-intel, network]
version: 1.0.0
---
## Purpose
This playbook takes the defensive view of the Sliver open-source adversary-emulation framework: how to recognize Sliver implants, sessions, and listener infrastructure in your environment, attribute them, and dismantle them. Sliver is legitimately used by red teams and unlawfully by threat actors; either way, defenders must be able to spot its artifacts. No instructions for deploying or operating Sliver are included.

## When to use
- Threat hunting for beaconing or implant activity after a suspected compromise.
- Triaging alerts for unusual TLS, mTLS, DNS, or HTTP traffic patterns on your network.
- Building detections after Sliver usage appears in threat-intelligence reporting for your sector.
- Validating that an authorized red-team engagement used Sliver only inside agreed scope.

## Prerequisites
- Access to network flow data, TLS handshake logs, or full-packet capture.
- Endpoint telemetry (EDR or Sysmon) covering process creation, network connections, and service installation.
- Threat-intelligence source with known Sliver signatures (open-source detection repositories, ATT&CK technique references).
- Familiarity with MITRE ATT&CK technique T1071 (Application Layer Protocol) and T1573 (Encrypted Channel).

## Procedure
1. Gather candidate implants and listeners. Collect suspicious binaries, memory images, or process metadata flagged by EDR; note listening ports, TLS certificates, and peer addresses.
2. Extract implant configuration statically. For a captured binary, look for embedded listener URLs, beacon intervals, jitter, and operator-server certificates. Record them as indicators.
3. Identify network signatures. Sliver listeners commonly terminate on HTTP, HTTPS, mTLS, DNS, or WireGuard channels. Look for periodic beaconing with fixed intervals and jitter, unusual JA3 hashes, self-signed certificates with distinctive subjects, and DNS query patterns tied to the framework.
4. Correlate endpoint behavior. Map implant execution to process trees: unusual service installs, scheduled tasks, DLL side-loading attempts, and outbound connections from non-browser processes.
5. Search historical telemetry. Pivot the extracted certificates, IPs, ports, and JA3 hashes across DNS logs, proxy logs, and NetFlow to size the footprint and find additional hosts.
6. Attribute and scope. Compare artifacts with threat-intelligence reporting; distinguish authorized red-team use (check engagement windows and scope letters) from unauthorized activity.
7. Contain. Isolate affected hosts, block listener infrastructure at the egress proxy and firewall, revoke credentials on impacted systems, and rotate any secrets the implant could have read.
8. Disrupt and monitor. After takedown, keep detections active for at least 30 days to catch re-beaconing from missed implants or backup listener profiles.

## Expected outputs
- Documented implant configuration (listener URLs, beacon interval, certificates) as shareable indicators.
- Detection rules covering network beacons, endpoint artifacts, and certificate patterns.
- Scoped list of affected hosts and accounts with containment status.
- Incident report noting whether activity was authorized (red team) or malicious.

## Pitfalls
- Self-signed TLS certificates are not unique to Sliver; require corroborating endpoint or beacon-interval evidence before concluding.
- Beacon intervals can be tuned to blend with normal traffic, so short-interval hunting alone will miss slow beacons.
- Confusing authorized red-team traffic with real attacks; always reconcile with engagement records before treating alerts as incidents.
- Implants can migrate listeners; a single blocked IP rarely ends the campaign.

## References
- MITRE ATT&CK: Command and Control tactics (TA0011), technique T1071 (Application Layer Protocol)
- MITRE ATT&CK: T1573 (Encrypted Channel)
- CISA guidance on adversary emulation and threat hunting
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
