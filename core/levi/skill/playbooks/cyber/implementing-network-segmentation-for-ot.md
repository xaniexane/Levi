---
skill_id: cyber_implementing_network_segmentation_for_ot
name: Implementing Network Segmentation for OT
description: Segment operational technology networks by Purdue level and risk — conduits, unidirectional gateways, and remote-access controls that respect process safety.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, ics, network, segmentation]
version: 1.0.0
---
## Purpose

Contain cyber risk in industrial environments without endangering the process. OT segmentation partitions the network along Purdue-model levels and risk boundaries so that a compromised enterprise workstation cannot reach a PLC, and a compromised HMI cannot reach the safety system — using conduits with explicit allowlists, unidirectional gateways where data only flows one way, and remote access that is monitored and temporary.

## When to use

- Remediating flat OT networks where IT and control systems share broadcast domains.
- Building or retrofitting plants, pipelines, utilities, or manufacturing lines.
- Enabling IT/OT convergence (cloud historians, analytics, vendor remote access) safely.
- Meeting IEC 62443 zone/conduit or NERC CIP ESP requirements.
- After incidents demonstrating lateral movement from IT into OT.

## Prerequisites

- Asset inventory with Purdue-level assignment and data-flow mapping between levels.
- Full-cycle traffic captures per conduit to discover undocumented flows before enforcing.
- Process-engineer and operations sign-off authority — OT segmentation changes can halt production; IT cannot unilaterally decide.
- Maintenance windows aligned with production schedules (turnarounds, batch gaps).
- Spare/test environment or lab replicating control network behavior for pre-deployment validation.

## Procedure

1. **Map the Purdue levels and trust boundaries.** Assign every asset to levels 0–5 (0 physical process, 1 control, 2 supervisory, 3 operations/DMZ, 4/5 enterprise). Draw the current actual connectivity — not the architecture diagram, the observed flows — and mark every crossing between levels as a conduit to be controlled.
2. **Insert the Level 3.5 industrial DMZ.** Place historians, patch servers, AV relays, and jump hosts in an OT DMZ between enterprise (L4/5) and control (L0–2). No direct connections bypass the DMZ: enterprise users reach OT only through the DMZ, and control systems initiate outbound to the DMZ (for historian replication) rather than accepting inbound.
3. **Define conduit allowlists.** For each conduit, specify permitted protocols, ports, directions, and endpoints — e.g., L3 historian pulls OPC UA from L2 on 4840; nothing initiates from L4 to L2. Default-deny everything else. Validate each rule against the traffic captures; undocumented vendor connections will surface here.
4. **Deploy unidirectional gateways where data flows one way.** For historian feeds, monitoring exports, and any strictly one-way flow, prefer data diodes or unidirectional gateways over firewalls — they make reverse-flow attacks physically impossible rather than policy-prohibited. Use them especially at the IT/OT boundary for high-consequence processes.
5. **Control remote access ruthlessly.** All vendor and remote-administrator access terminates in the DMZ jump hosts with MFA, session recording, and time-boxed approvals — no direct VPN into the control network, no persistent vendor accounts. Every session is logged and reviewed; standing vendor access is removed.
6. **Segment within levels where risk demands.** Separate safety instrumented systems (SIS) from basic process control even within L1; separate process units or lines so a compromise in one does not cascade. Wireless (including IIoT sensors) gets its own segments with distinct authentication.
7. **Monitor every conduit.** Mirror conduit traffic to OT-aware IDS/NSM (Nozomi, Claroty, Dragos, or Suricata with OT rulesets) with protocol-aware parsing — a generic IT IDS misses Modbus function-code abuse. Alert on new flows (first-seen connections across conduits are high-value detections) and on policy violations.
8. **Govern changes permanently.** Every new connection, device, or vendor engagement crossing a conduit goes through OT change control with security review. Audit conduit rules against observed traffic quarterly; conduits decay without maintenance.

## Expected outputs

- Purdue-mapped asset inventory with observed (not assumed) data flows.
- Industrial DMZ architecture with documented conduits and allowlists.
- Unidirectional gateway deployments for one-way flows.
- Remote-access architecture with MFA, session recording, and time-boxed approvals.
- OT-aware IDS monitoring each conduit with first-seen alerting; change-control procedure.

## Pitfalls

- **Segmenting from diagrams instead of captures.** Architecture diagrams omit the engineer's laptop, the vendor's cellular modem, and the "temporary" connection from 2019. Capture first, segment second.
- **Blocking safety or control traffic.** An overzealous firewall rule between L1 and L2 can trip a process. Every deny rule near control traffic needs process-engineer review and staged rollout (monitor → enforce).
- **Treating the DMZ as a formality.** A DMZ with allow-any rules between tiers is a speed bump, not a boundary. Each DMZ tier transition needs its own allowlist.
- **Ignoring serial and wireless.** Segmentation projects focus on Ethernet while serial links, cellular modems, and plant Wi-Fi bypass everything. Inventory all communication paths, not just IP.
- **One-time project mindset.** OT environments change with every turnaround and vendor visit. Without ongoing change control, the segmented network re-flattens within a year.

## References

- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- IEC 62443-3-2 (zones and conduits) — via IEC/ISA
- CISA ICS advisories and OT segmentation guidance — https://www.cisa.gov/topics/industrial-control-systems
- MITRE ATT&CK for ICS — https://attack.mitre.org/techniques/ics/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
