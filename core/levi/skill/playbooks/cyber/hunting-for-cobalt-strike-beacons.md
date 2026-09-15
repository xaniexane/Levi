---
skill_id: cyber_hunting_for_cobalt_strike_beacons
name: Hunting for Cobalt Strike Beacons
description: Detect Cobalt Strike beacons via network fingerprints (JA3, malleable C2 artifacts), memory indicators, and behavioral telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, c2, malware]
version: 1.0.0
---
## Purpose

Cobalt Strike beacons are the post-exploitation payload of choice for both
red teams and ransomware affiliates. This defensive playbook covers
detecting beacons in your environment: network fingerprints (including
default and malleable-C2 profiles), host/memory indicators, and the
operational patterns beacons exhibit — so you can find real intrusions and
distinguish them from authorized red-team activity.

## When to use

- Investigating suspected post-exploitation activity or ransomware
  precursor behavior.
- Threat hunting after intel reports Cobalt Strike use in your sector.
- Tuning detections using traffic from an authorized red-team
  engagement (with their malleable profile documented).
- Triaging EDR alerts for beacon-like process injection or named-pipe
  C2.

## Prerequisites

- Network telemetry: proxy/TLS logs with JA3/JA4 fingerprints, HTTP
  header logs, DNS logs.
- Endpoint telemetry: Sysmon (process creation, network, named pipes),
  EDR with memory-visibility, PowerShell/AMSI logs.
- Knowledge of which red-team engagements are active (to avoid
  self-inflicted incidents) and their documented C2 profiles.
- Threat intel on current beacon hosting infrastructure and TTPs.

## Procedure

1. **Know the default fingerprints.** Study the well-documented default
   beacon indicators: default JA3 hashes, characteristic HTTP
   URI/check-in patterns, default named pipes, and default process-
   injection behaviors. Defaults are the low-hanging fruit — many
   real intrusions still use them.
2. **Hunt TLS fingerprints.** Query proxy/TLS logs for JA3/JA3S hashes
   associated with beacons, rare across your fleet. Correlate with
   destination reputation: beacon TLS to newly registered or
   bulletproof-hosted infrastructure is high priority.
3. **Hunt HTTP C2 patterns.** Look for periodic HTTP(S) check-ins with
   beacon-like traits: fixed-interval GETs/POSTs, unusual URI structures,
   distinctive headers or cookie patterns, and small symmetric payloads.
   Malleable profiles change these — so pair signature hunting with the
   behavioral beaconing analysis from the frequency-analysis playbook.
4. **Hunt named-pipe and SMB beacons.** Query Sysmon event 17/18 for
   beacon-associated pipe names and anomalous pipe creation on
   workstations; look for lateral-movement chains where a beacon spawns
   remote sessions (SMB beaconing between hosts).
5. **Hunt memory and injection indicators.** Triage EDR alerts for
   reflective DLL loading, process hollowing, and unsigned code in
   legitimate processes (explorer, svchost children). Memory scans for
   beacon configuration blocks can confirm — coordinate with IR before
   broad memory collection.
6. **Correlate the full chain.** Beacons rarely arrive alone: precede
   the beacon with its delivery (phishing, exploit, LOLBin) and follow
   with its actions (credential access, lateral movement, staging).
   Build the timeline to scope the intrusion.
7. **Distinguish red-team from real.** Maintain a registry of authorized
   engagements with their C2 infrastructure and profiles. Beacon
   activity matching the registry during the engagement window is
   expected; everything else is treated as hostile until proven
   otherwise.
8. **Contain and convert to detection.** On confirmation: isolate hosts,
   block C2 at egress, extract the beacon configuration for IOCs
   (C2 URLs, keys, spawn-to processes), and build durable detections
   from the observed profile — not just the default signatures.

## Expected outputs

- Hunt findings: beacon hosts with network, host, and memory evidence.
- Extracted beacon configurations and IOC packages.
- Containment records and scoping timelines.
- Durable detections tuned to observed (not just default) profiles.
- An authorized-engagement registry to prevent false incidents.

## Pitfalls

- Malleable C2 profiles defeat default signatures — behavioral
   detection (periodicity, injection) is the durable layer.
- JA3 collisions with legitimate software cause false positives —
   always corroborate with host telemetry.
- Attackers use legitimate cloud infrastructure for C2 — reputation-
   only blocking misses it; behavior is the signal.
- Forgetting the red-team registry turns your own testers into an
   incident — keep it current and visible to the SOC.
- Beacon configs extracted from memory contain keys and URLs — handle
   as sensitive intel, not ticket fodder.

## References

- MITRE ATT&CK: T1071.001 (Web Protocols), T1055 (Process Injection),
  T1573 (Encrypted Channel)
- CISA: guidance on detecting Cobalt Strike abuse
- Industry research on beacon network fingerprints and malleable C2
  detection
- JA3/JA4 fingerprinting documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
