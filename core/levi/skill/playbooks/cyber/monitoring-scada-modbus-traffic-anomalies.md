---
skill_id: cyber_monitoring_scada_modbus_traffic_anomalies
name: Monitoring SCADA Modbus Traffic Anomalies
description: Detect anomalous Modbus traffic in OT networks for early warning of process manipulation.
risk: low
permissions: []
requires_confirmation: false
tags: [ics, ot-security, network-monitoring]
version: 1.0.0
---
## Purpose
This playbook builds passive monitoring for Modbus/TCP traffic in operational technology networks: baselining normal control-system behavior and alerting on anomalies that indicate reconnaissance, manipulation, or malware — without ever injecting traffic into the control network.

## When to use
- OT networks lack visibility into control-system protocol traffic.
- You need to detect unauthorized engineering workstation activity or rogue masters.
- Supporting NERC CIP, IEC 62443, or similar OT security requirements.

## Prerequisites
- Passive network taps or SPAN ports on OT network segments; no active scanning of control devices.
- OT asset inventory: PLCs, RTUs, HMIs, historians, and their normal communication patterns.
- Coordination with OT engineering: they own process safety and must approve monitoring changes.

## Procedure
1. **Capture passively.** Deploy a passive sensor with a Modbus dissector (Zeek, Snort with OT rulesets, or OT-specific NDR); verify zero packet injection into the control network.
2. **Baseline normal behavior.** Learn the legitimate master/slave pairs, function codes used, polling intervals, and register ranges per process cell over several production cycles.
3. **Define anomaly rules.** Alert on: new masters, write commands (function codes 5, 6, 15, 16) outside maintenance windows, reads of unusual register ranges, and protocol errors indicating fuzzing or scanning.
4. **Correlate with IT/OT boundary.** Cross-reference anomalies with firewall logs at the IT/OT boundary and engineering workstation activity.
5. **Build the OT triage workflow.** Define who gets paged, how to verify with process engineers before acting, and what "do not touch" means during an active process.
6. **Tune with engineering input.** Review every alert with OT staff initially; maintenance activities and process changes cause most false positives.
7. **Retain for forensics.** Keep full packet captures for a defined window; OT incidents are rare but investigations need the raw data.

8. **Extend to other OT protocols.** Once Modbus monitoring is mature, apply the same passive-baseline approach to DNP3, S7, or EtherNet/IP present in your environment.
9. **Include OT in incident exercises.** Run tabletop exercises with both IT responders and process engineers so the first joint incident is not the first joint conversation.

## Expected outputs
- Passive Modbus monitoring with baselined allow-profiles per process cell.
- Anomaly detections tuned with OT engineering sign-off.
- OT incident triage workflow respecting process safety constraints.
- Example: an alert fires for Modbus write commands to a PLC outside a maintenance window; the triage workflow confirms with process engineering within 15 minutes whether it is authorized work or a genuine anomaly.

## Pitfalls
- Active scanning or blocking in OT: you can cause physical process disruption.
- IT analysts triaging OT alerts without process context, misreading normal operations as attacks.
- Monitoring without engineering partnership: alerts get ignored and the program dies.

- Deploying the sensor with an IP address on the OT network "for management" that becomes a bridge between IT and OT; use data diodes or strictly isolated management.
- Alerting on Modbus function codes without understanding the process; a write command during a batch change is normal, and context is everything.

## References
- CISA ICS advisories and guidance (cisa.gov/ics).
- NIST SP 800-82 Rev. 3, Guide to Operational Technology Security.
- ISA/IEC 62443 standards series — industrial automation security.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
