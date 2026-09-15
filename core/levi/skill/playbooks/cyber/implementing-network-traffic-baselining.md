---
skill_id: cyber_implementing_network_traffic_baselining
name: Implementing Network Traffic Baselining
description: Establish statistical and behavioral baselines of normal network traffic so anomalies — beacons, exfiltration, lateral movement — stand out to detection.
risk: info
permissions: []
requires_confirmation: false
tags: [network, detection, baselining, hunting]
version: 1.0.0
---
## Purpose

Define "normal" rigorously so "abnormal" means something. Traffic baselining measures the steady-state behavior of the network — volumes, protocols, peer relationships, timing patterns, and byte ratios per host, segment, and service — creating the reference that anomaly detection, hunting hypotheses, and alert triage all depend on. Without a baseline, every anomaly detector is just a random alert generator.

## When to use

- Before tuning NDR, UEBA, or any behavioral detection — baselines are the prerequisite input.
- Establishing hunt team capability: baselines generate the hypotheses ("which hosts deviate from their peer group this week?").
- Reducing false positives by replacing static thresholds with environment-specific norms.
- Post-network-change validation: confirming a migration or new application behaves as expected.
- Meeting expectations for continuous monitoring with anomaly detection (NIST SP 800-137).

## Prerequisites

- Network telemetry sources: NetFlow/IPFIX/sFlow from routers and switches, firewall logs, DNS logs, proxy logs, and ideally full session metadata (Zeek/Arkime).
- SIEM or analytics platform capable of aggregations over 30–90 days of telemetry.
- Asset context: host roles, peer groups (all web servers should behave alike), and business cycles (month-end batch jobs, backups) that explain periodic deviations.
- Defined measurement windows covering full business cycles — a baseline built on two quiet weeks mislabels month-end as an attack.
- Stakeholder agreement on which deviations trigger alerts vs. hunt leads vs. informational notes.

## Procedure

1. **Select the telemetry and the entities.** Baseline at multiple grains: per host (top talkers, protocols, ports), per peer-group (role-based cohorts), per segment/VLAN, and per critical service. Minimum viable telemetry: flow records (5-tuple, bytes, packets, duration, TCP flags), DNS query logs, and proxy/web logs. Add Zeek protocol logs where available for application-layer baselines.
2. **Capture a full business cycle.** Collect 30–90 days covering month-end/quarter-end processing, patch windows, backup schedules, and any seasonal patterns. Document known events in the window (migrations, incidents, holidays) so they don't poison the baseline — or rather, so you know exactly how they shaped it.
3. **Compute the baseline statistics.** For each entity and metric, calculate central tendency and spread (mean/median, standard deviation, percentiles), plus categorical profiles: the set of external destinations a host normally contacts, its normal ports and protocols, typical session durations and byte ratios. Store baselines as versioned artifacts, not tribal knowledge.
4. **Define peer groups.** Group hosts by role and expected behavior (domain controllers, web servers, developer workstations, printers). Peer-group comparison catches the compromised web server behaving unlike its siblings even when its absolute numbers look unremarkable — deviation-from-peers beats deviation-from-self for many attack patterns.
5. **Build the anomaly use cases.** Convert baselines into detections: new external destination for a server (first-seen), byte-ratio inversion (more outbound than inbound on a workstation), beaconing periodicity (regular intervals to rare destinations), protocol-on-unexpected-port, and volume deviations beyond N standard deviations. Tune thresholds per peer group, not globally.
6. **Validate against known-good and known-bad.** Replay historical incident traffic (if available) through the baseline logic to confirm it would have fired; run during a normal week to measure false-positive rates. A baseline that fires on every backup window is a baseline nobody trusts.
7. **Operationalize the refresh cycle.** Recompute baselines monthly or after significant changes (new applications, network redesigns, mergers). Alert on baseline drift itself — a peer group whose profile shifts suddenly may indicate a compromised member or an undocumented change, both worth investigating.
8. **Feed hunting and triage.** Publish baseline dashboards for analysts: top deviating hosts this week, new external destinations per segment, protocol anomalies. Make "check the baseline" a step in the alert-triage runbook — context from baselines separates real incidents from weird-but-legitimate faster than any single alert.

## Expected outputs

- Versioned baseline artifacts per entity grain (host, peer group, segment, service) with methodology documented.
- Peer-group definitions with behavioral profiles.
- Anomaly detection use cases with per-group tuned thresholds.
- Validation results (historical incidents detected, false-positive rates measured).
- Refresh cadence and baseline-drift alerting; analyst dashboards.

## Pitfalls

- **Too-short measurement windows.** Two weeks of data makes month-end batch jobs look like data exfiltration. Cover full business cycles or accept the false positives.
- **Global thresholds.** A single "alert above X GB" threshold either misses server exfiltration or floods on backup traffic. Thresholds must be per-entity or per-peer-group.
- **Poisoned baselines.** Building the baseline during an active undetected compromise bakes attacker behavior into "normal." Sanity-check the baseline window for known incidents and obvious anomalies before freezing it.
- **Static baselines.** Networks change; a baseline frozen for a year increasingly describes a network that no longer exists. Refresh on cadence and on change.
- **Alerting on everything.** Not every deviation deserves a page. Tier the outputs: paging for high-confidence malicious patterns, hunt leads for interesting deviations, dashboards for the rest.

## References

- NIST SP 800-137, "Information Security Continuous Monitoring" — https://csrc.nist.gov/publications/detail/sp/800-137/final
- Zeek network security monitor documentation — https://docs.zeek.org/
- MITRE ATT&CK T1048 (Exfiltration Over Alternative Protocol), T1071.004 (DNS) — behaviors baselining detects — https://attack.mitre.org/
- SANS hunting and baselining methodology references
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
