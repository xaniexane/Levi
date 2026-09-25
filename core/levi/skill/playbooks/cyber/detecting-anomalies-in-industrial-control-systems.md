---
skill_id: cyber_detecting_anomalies_in_industrial_control_systems
name: Detecting Anomalies in Industrial Control Systems
description: Detect anomalous behavior in ICS/OT networks with passive monitoring, protocol baselining, and safety-aware alerting.
risk: info
permissions: []
requires_confirmation: false
tags: [ics, ot, detection]
version: 1.0.0
---
## Purpose

Detect cyber anomalies in industrial control system networks — unauthorized engineering commands, unexpected protocol behavior, new devices — using passive monitoring that never interferes with the process. In OT, the monitoring must never become the incident.

## When to use

- Standing up OT security monitoring for the first time (greenfield SOC-for-OT).
- Investigating suspected compromise of control networks or engineering workstations.
- Meeting regulatory or standards requirements (NERC CIP, IEC 62443 monitoring clauses).
- Validating segmentation between IT and OT after a network redesign.

## Prerequisites

- Written authorization from operations/engineering — OT monitoring is a joint IT/OT activity, never unilateral.
- Passive capture infrastructure: network taps or SPAN ports on OT segments (never inline devices that could fail closed and stop the process).
- A process-aware baseline partner: an engineer who can say "that command is normal during a turnaround."
- Asset inventory of OT devices: PLCs, RTUs, HMIs, historians, engineering workstations, with their normal communication patterns.

## Procedure

1. **Capture passively and prove zero impact.** Deploy taps or SPAN (never inline IPS) on OT network segments. Verify with operations that the monitoring introduces no latency, no new failure modes, and no active scanning of OT devices — active scanning has crashed PLCs; passive capture has not.
2. **Baseline normal OT traffic.** OT networks are beautifully predictable: the same devices talk the same protocols on the same schedule. Record for 30+ days: which hosts communicate, which industrial protocols and function codes are used, normal command rates, and maintenance-window patterns. This baseline is your detection model — deviations are the alerts.
3. **Alert on engineering-action anomalies.** Flag: programming/configuration commands to PLCs outside maintenance windows, firmware uploads, logic downloads, and setpoint changes from unexpected hosts. These are the OT equivalent of "new admin activity" — rare, impactful, and almost always worth investigating.
4. **Detect new and rogue devices.** Alert on any new MAC/IP on the OT segment, new devices speaking industrial protocols, and engineering workstations connecting from unusual locations. In a static OT network, a new device is an event, not background noise.
5. **Monitor the IT/OT boundary ruthlessly.** Alert on: any traffic crossing the boundary outside the allowlisted conduits (historian replication, specific jump hosts), new protocols crossing the boundary, and volume anomalies on existing conduits. The boundary is where IT-borne threats enter OT — treat every anomaly here as high priority.
6. **Watch for protocol misuse and anomalies.** Flag malformed industrial-protocol packets, unusual function codes, commands to devices that never receive commands (sensors suddenly getting writes), and protocol tunneling (industrial protocols over unexpected ports). Pair with an OT-aware IDS (Claroty, Nozomi, Dragos, or Snort/Suricata with ICS rulesets) for protocol-depth parsing.
7. **Correlate with physical process data.** Where possible, compare network commands against process reality: a command to open a valve should correspond to a valve opening. Commands with no physical effect — or physical changes with no network command — are both anomalies worth investigating with operations.
8. **Build the OT incident playbook with operations.** Define in advance: who can authorize isolating an OT segment (operations, not IT alone), how to preserve forensic evidence without stopping the process, and the safety interlocks that must never be touched by responders. Exercise it in a tabletop with both IT and OT at the table.

## Expected outputs

- Passive OT monitoring with a 30-day behavioral baseline and protocol-aware alerting.
- High-priority alerts on engineering actions, new devices, and IT/OT boundary violations.
- A joint IT/OT incident playbook with defined isolation authority and safety constraints.

## Pitfalls

- Active scanning or inline prevention in OT — the monitoring becomes the outage.
- Alerting without an operations partner — IT-only triage misreads normal process behavior as attacks.
- Treating OT like IT — the baseline approach works because OT is deterministic; don't import IT's anomaly models wholesale.
- Ignoring maintenance windows — every alert during a turnaround is noise unless you model the windows.
- Forensic collection that stops the process — plan evidence preservation with operations before the incident.

## References

- NIST SP 800-82 Rev. 3 (Guide to OT Security)
- IEC 62443 series — industrial automation and control systems security
- CISA ICS advisories and OT monitoring guidance
- MITRE ATT&CK for ICS — technique mapping for OT detections
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
