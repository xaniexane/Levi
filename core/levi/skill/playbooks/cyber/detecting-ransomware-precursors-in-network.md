---
skill_id: cyber_detecting_ransomware_precursors_in_network
name: Detecting Ransomware Precursors in Network
description: Detect ransomware staging activity in network traffic before encryption begins.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, network, detection]
version: 1.0.0
---
## Purpose

Ransomware operators spend days to weeks inside networks before encrypting: reconnaissance, lateral movement, exfiltration, and backup targeting. This playbook focuses on the network-visible precursors — the activity that, caught early, lets defenders evict the intruder before a single file is encrypted.

## When to use

- You want early-warning ransomware detection, not just encryption alerts.
- Threat intel describes ransomware affiliates active in your sector.
- After-action review showed network precursors were missed before encryption.
- Building ransomware-specific network hunting use cases.

## Prerequisites

- Network visibility: Zeek/IDS logs, firewall logs, NetFlow, DNS logs, proxy logs — covering east-west and egress.
- Baseline of normal internal and external traffic patterns.
- Ransomware-affiliate TTP intelligence (which tools, which C2 patterns).
- Backup infrastructure network map (what 'backup targeting' looks like in your environment).

## Procedure

1. Map the precursor kill chain to network signals. Ransomware staging follows a pattern: initial access (phishing/VPN/RDP anomalies) → discovery (internal recon, AD enumeration) → lateral movement (SMB/RDP fan-out, PsExec) → exfiltration (large egress to cloud storage or attacker infra) → backup destruction → encryption. Define a network detection for each stage — the chain is the use case.
2. Detect discovery and lateral movement early. Alert on: internal reconnaissance (port/host sweeps, AD enumeration via LDAP), credential-access traffic (DCSync replication anomalies, LSASS-dump precursors), and lateral fan-out (SMB/RDP/WinRM from workstations to servers). These stages last days — the longest window to catch the intrusion.
3. Detect exfiltration staging. Double-extortion ransomware exfiltrates before encrypting: alert on large-volume egress to rare external destinations, connections to file-sharing/cloud-storage from servers (not just workstations), DNS tunneling indicators, and data-staging (internal bulk SMB copies to a collection host followed by egress). Exfiltration is often the last detectable stage before impact.
4. Watch backup and recovery targeting. Alert on: connections to backup servers/consoles from unusual hosts, backup-agent disablement traffic, mass deletion commands against backup repositories, and access to cloud backup consoles from anomalous locations. Backup targeting is the final precursor — treat it as an imminent-encryption signal.
5. Build a ransomware-precursor correlation. Group alerts per host/subnet across stages in a rolling window: recon + lateral + exfil signals on one host within days = high-confidence ransomware staging, escalated immediately regardless of any single alert's severity. Single-stage alerts are hunts; multi-stage correlation is an incident.
6. Respond to precursors with eviction urgency. Confirmed staging means: isolate affected hosts, reset credentials for exposed accounts, block C2/exfil infrastructure, hunt for persistence and additional footholds, and verify backup integrity offline. Speed matters more than completeness at this stage — evict first, then do the full forensic accounting.

## Expected outputs

- Per-stage network detections mapped to the ransomware staging chain.
- Multi-stage correlation rule: recon + lateral + exfil groupings with escalation.
- Backup-targeting detections with imminent-encryption response criteria.
- Eviction runbook: isolation, credential reset, infrastructure blocking, backup verification.

## Pitfalls

- Single-precursor alerts are low severity alone — the correlation across stages is what makes this work.
- Exfiltration to legitimate cloud services (OneDrive, S3) blends with business traffic — baseline per host role.
- Slow, distributed staging evades per-host thresholds — aggregate at subnet/campaign level too.
- Treating precursor detection as 'monitoring' without an eviction runbook wastes the early warning.
- Backup-targeting alerts must reach the backup team directly — generic SOC queues are too slow.

## References

- CISA StopRansomware guidance (cisa.gov/stopransomware); MITRE ATT&CK T1486 (Data Encrypted for Impact), T1048 (Exfiltration Over Alternative Protocol) — https://attack.mitre.org/; NIST SP 800-61 Rev. 2
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
