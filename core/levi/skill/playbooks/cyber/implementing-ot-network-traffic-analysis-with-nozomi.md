---
skill_id: cyber_implementing_ot_network_traffic_analysis_with_nozomi
name: Implementing OT Network Traffic Analysis with Nozomi
description: Deploy Nozomi Networks for OT asset discovery, protocol-aware traffic analysis, anomaly detection, and threat intelligence in industrial environments.
risk: info
permissions: []
requires_confirmation: false
tags: [ot, ics, network, monitoring, nozomi]
version: 1.0.0
---
## Purpose

Gain continuous, passive visibility into OT networks: what assets exist, how they communicate, and when behavior deviates — without touching the control systems. Nozomi Networks sensors passively parse industrial protocols (Modbus, DNP3, EtherNet/IP, S7, OPC UA, and dozens more), build the asset inventory automatically, baseline normal behavior, and alert on anomalies and known threats, feeding both the SOC and OT engineers with protocol-aware context.

## When to use

- Discovering the true OT asset inventory (the spreadsheet is always wrong).
- Detecting unauthorized devices, new connections, and anomalous control-system behavior.
- Meeting IEC 62443 monitoring or NERC CIP ESP monitoring expectations.
- Supporting OT incident response with historical protocol-level evidence.
- Validating segmentation: proving conduits carry only expected traffic.

## Prerequisites

- SPAN/tap access or network packet brokers at OT choke points (control network uplinks, DMZ conduits, remote-access paths) — passive only; no in-line deployment in control networks without extreme care.
- Asset inventory seed data (whatever exists) to reconcile against discovered assets.
- Protocol list for the environment so sensor protocol support can be confirmed in advance.
- SIEM/SOAR integration endpoints and alert-routing design (which alerts go to SOC vs. OT engineering).
- Maintenance coordination: sensor deployment touches network infrastructure in sensitive areas.

## Procedure

1. **Plan sensor placement for full coverage.** Position sensors (physical Guardian appliances, virtual, or cloud) to see every OT conduit: uplinks from cell/area zones, the industrial DMZ, historian connections, and remote-access paths. Partial coverage creates blind spots that investigations will discover at the worst time; document any uncovered segments explicitly.
2. **Deploy passively and verify no impact.** Connect via SPAN/tap with receive-only cabling where possible. Validate with OT engineering that the deployment introduces zero in-line risk — passive monitoring must be provably unable to affect control traffic. Get the sign-off in writing; it matters for both safety cases and blame allocation.
3. **Let discovery build the inventory, then reconcile.** Allow 2–4 weeks of learning for asset discovery and protocol identification. Reconcile discovered assets against the official inventory: unknown devices are either undocumented (update the inventory) or unauthorized (investigate). Firmware versions, serial numbers, and protocol roles discovered passively become the authoritative asset record.
4. **Tune anomaly baselines per zone.** Nozomi learns normal behavior (communication patterns, protocol function codes, timing). Work with OT engineers to validate the baseline through a full production cycle, then tune: whitelist expected engineering activities (firmware uploads during turnarounds), and set alert thresholds that respect process reality — a "new device" during commissioning is normal, at 2 a.m. on a Sunday is not.
5. **Operationalize the alert taxonomy.** Route alerts by type: known-malware/IOC matches and OT-protocol attacks (unauthorized Modbus writes, PLC stop commands) → immediate SOC + OT engineering response; asset/behavior anomalies → OT engineering triage queue; misconfigurations (plaintext protocols, default credentials observed) → remediation backlog. Define SLAs per class.
6. **Integrate threat intelligence.** Enable Nozomi's OT threat intelligence feeds for ICS-specific IOCs and vulnerability correlation (e.g., alert when a discovered asset runs firmware with a known CVE). Correlate with IT intel: an IT-side compromise of a vendor with OT remote access should raise OT alert sensitivity.
7. **Use it for segmentation validation and IR.** Continuously verify conduit allowlists against observed traffic — any flow violating the zone/conduit design is either a misconfiguration or an incident. During IR, use historical protocol data for scoping: which controllers talked to the compromised engineering workstation, what function codes were issued, when.
8. **Maintain and review.** Keep sensor software and threat content updated, re-baseline after process changes, and review the asset inventory quarterly with OT engineering. Report metrics: asset coverage, mean time to detect OT anomalies, and misconfiguration remediation rates.

## Expected outputs

- Sensor coverage map with documented placement rationale and any blind spots.
- Reconciled OT asset inventory with protocol roles and firmware data.
- Tuned anomaly baselines validated through a production cycle.
- Alert routing matrix (SOC vs. OT engineering) with SLAs.
- Segmentation-validation reports and IR scoping procedures using historical data.

## Pitfalls

- **SPAN port oversubscription.** An overloaded SPAN port drops the exact packets you need most during an incident. Size SPAN capacity with headroom and monitor for drops.
- **Alerting OT engineers on IT noise.** Flooding process engineers with generic IT-style alerts trains them to ignore the platform. Tune ruthlessly and route appropriately.
- **Baseline built during abnormal operations.** Learning during commissioning, turnarounds, or an active incident bakes anomalies into "normal." Choose the learning window deliberately and re-baseline after major changes.
- **Treating discovery as a one-time event.** OT environments change with every vendor visit and turnaround. Continuous discovery is the point; a quarterly spreadsheet export is not.
- **No integration with IT SOC.** OT alerts isolated from IT context miss the full attack chain (IT compromise → OT pivot). Correlate across both, with clear handoff procedures.

## References

- Nozomi Networks documentation — https://www.nozominetworks.com/
- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- CISA OT monitoring guidance — https://www.cisa.gov/topics/industrial-control-systems
- MITRE ATT&CK for ICS — https://attack.mitre.org/techniques/ics/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
