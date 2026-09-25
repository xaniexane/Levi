---
skill_id: cyber_detecting_attacks_on_scada_systems
name: Detecting Attacks on SCADA Systems
description: Detect attacks on SCADA environments with passive protocol monitoring, command baselining, and safety-first response.
risk: info
permissions: []
requires_confirmation: false
tags: [ics, scada, detection]
version: 1.0.0
---
## Purpose

Detect cyber attacks against SCADA systems — unauthorized control commands, protocol abuse, and engineering-workstation compromise — with passive monitoring and detection logic built for the deterministic nature of control networks. Safety first: detection must never endanger the process.

## When to use

- Deploying security monitoring in electric, water, oil/gas, or manufacturing SCADA environments.
- Investigating suspected unauthorized control actions or SCADA malware.
- Meeting NERC CIP or IEC 62443 monitoring requirements.
- Validating SCADA network segmentation and remote-access controls.

## Prerequisites

- Operations and safety engineering sponsorship — SCADA security is a joint discipline.
- Passive capture on SCADA segments (taps/SPAN); OT protocol parsers (Modbus, DNP3, IEC 60870-5-104, OPC).
- Asset inventory: MTU/SCADA servers, RTUs/PLCs, communication paths (serial, IP, cellular), and normal polling patterns.
- Defined safety constraints: which responses are allowed during an incident (isolation authority, fail-safe positions).

## Procedure

1. **Map the SCADA communication architecture.** Document every master-to-remote path: which SCADA server polls which RTUs, over which protocol and transport, at what intervals. Include dial-up/cellular and serial links — attackers use the forgotten paths. This map is the foundation of all detection.
2. **Baseline polling and command patterns.** SCADA is the most predictable traffic on earth: cyclic polls, scheduled reports, rare control commands. Record 30+ days of: poll intervals per device, normal command types and rates, and maintenance-window behavior. Alert on deviations: new commands, changed intervals, polls from new sources.
3. **Detect unauthorized control operations.** Alert on: control commands (breaker operations, setpoint changes, mode switches) outside maintenance windows, commands from hosts that never issue commands (a historian suddenly sending controls is an attack), and command sequences that violate operating procedures. These alerts go directly to operations as well as the SOC.
4. **Monitor engineering and vendor access.** Alert on: remote-access sessions to the SCADA network outside approved windows, new VPN/dial-up connections, vendor accounts active without a work order, and engineering workstation behavior changes (new software, USB insertions, internet browsing on an OT host).
5. **Detect protocol-level attacks.** With OT-aware IDS, alert on: malformed Modbus/DNP3/104 packets, function codes never used in your environment, broadcast storms, replayed commands (same sequence/timestamps), and protocol tunneling. Maintain an allowlist of function codes per device type.
6. **Watch for SCADA malware indicators.** Hunt for: known ICS malware signatures and behaviors (wiper components, PLC logic uploaders), living-off-the-land on SCADA servers (PowerShell, PsExec, credential dumping), and reconnaissance patterns (OPC enumeration, network scanning from inside the SCADA segment — scanning is never normal here).
7. **Correlate cyber with physical.** Work with operations to compare: do network commands match physical operations? Investigate mismatches in both directions. A breaker that opened with no SCADA command, or a SCADA command with no physical effect, are both high-priority anomalies.
8. **Exercise the SCADA incident playbook.** Define: who authorizes control-system isolation, how to preserve evidence from serial/IP captures, fail-safe versus fail-secure decisions per process, and regulatory notification triggers (NERC CIP, CISA). Tabletop with IT, OT, operations, and safety engineering together.

## Expected outputs

- A SCADA communication map with 30-day baselines and deviation alerting.
- Detections for unauthorized control commands, protocol abuse, and engineering-access anomalies.
- A joint IT/OT incident playbook with defined isolation authority and safety constraints.

## Pitfalls

- Active scanning of RTUs/PLCs — legacy devices crash; passive only.
- IT-led triage without operations — normal control actions look like attacks to outsiders.
- Ignoring serial and dial-up paths — the IP network isn't the whole attack surface.
- Alerting on polling — the baseline must model normal polling or every poll is noise.
- No fail-safe plan — isolating a SCADA segment without knowing the process consequences is dangerous.

## References

- NIST SP 800-82 Rev. 3 (Guide to OT Security)
- MITRE ATT&CK for ICS — full technique matrix for SCADA detections
- NERC CIP standards (CIP-005, CIP-007, CIP-008) for applicable entities
- CISA ICS advisories and alerts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
