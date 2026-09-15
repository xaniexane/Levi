---
skill_id: cyber_detecting_dnp3_protocol_anomalies
name: Detecting DNP3 Protocol Anomalies
description: Detect malicious DNP3 activity in OT networks with function-code baselining and unsolicited-message monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [ics, ot, detection]
version: 1.0.0
---
## Purpose

Detect attacks against DNP3 (Distributed Network Protocol 3) — the SCADA protocol of electric utilities and water systems — by baselining legitimate master/outstation behavior and alerting on protocol misuse. DNP3 has no authentication in its common deployments; monitoring is the security layer.

## When to use

- Monitoring electric, water/wastewater, or oil/gas SCADA networks that use DNP3.
- Investigating suspected manipulation of DNP3-controlled equipment.
- Validating DNP3 Secure Authentication deployment (IEEE 1815-2012).
- Meeting NERC CIP monitoring requirements for applicable systems.

## Prerequisites

- Passive network capture on DNP3 segments with a DNP3-aware parser (Zeek DNP3 analyzer, OT IDS, or Wireshark dissectors).
- Inventory of DNP3 masters and outstations: addresses, expected function codes, polling schedules.
- Operations partnership to distinguish legitimate control actions from attacks.
- Baseline capture of 30+ days of normal DNP3 traffic.

## Procedure

1. **Map the DNP3 architecture.** Document every master-outstation pair: DNP3 addresses, transport (TCP, UDP, serial), polling intervals, and which function codes each master legitimately uses. Include backup masters and engineering access paths — attackers use the forgotten ones.
2. **Baseline function-code usage.** DNP3 function codes define what's allowed: reads (129), writes (2), selects (3), operates (4), direct-operate (5/6), freeze/clear (7-13), restarts (14). Record which codes each master sends to each outstation and how often. Control codes (3, 4, 5, 6) from unexpected sources or at unexpected times are the critical alerts.
3. **Detect unauthorized control operations.** Alert on: operate/direct-operate commands outside maintenance windows, control commands from hosts that aren't the designated master, and control sequences that skip the select-before-operate pattern your environment normally uses. Correlate with operations — a legitimate switching order looks identical on the wire to an attack; the difference is authorization.
4. **Monitor for protocol abuse.** Alert on: malformed DNP3 packets, function codes never seen in your baseline, broadcast commands (address 0xFFFF) from unexpected sources, time-synchronization abuse (function code 23 / LAN procedure), and unsolicited responses (130) from outstations that shouldn't send them. These indicate scanning, fuzzing, or manipulation.
5. **Watch for reconnaissance.** Alert on: integrity polls of unusual scope, reads of device-attribute objects (object group 0 — fingerprinting), and sequential address scanning. DNP3 reconnaissance is rare in normal operations — the master knows its outstations; scanning means someone is mapping.
6. **Validate Secure Authentication where deployed.** If DNP3 Secure Authentication (SAv5/SAv6) is in use, monitor for: authentication failures, aggressive-mode usage (weaker — flag it), and fallback to unauthenticated operation. Authentication failures followed by successful unauthenticated commands suggest downgrade attacks or misconfiguration.
7. **Correlate with physical process state.** Work with operations to verify that DNP3 commands correspond to authorized work: a breaker operation on the wire should match a switching order. Investigate mismatches immediately — in OT, the physical process is the ground truth that network monitoring serves.

## Expected outputs

- A DNP3 master/outstation map with function-code baselines per pair.
- Detections for unauthorized controls, protocol abuse, reconnaissance, and auth failures.
- Operations-correlated verification that commands match authorized work.

## Pitfalls

- No DNP3-aware parser — generic IDS sees TCP packets, not function codes; the protocol layer is where the attacks live.
- Alerting without operations partnership — legitimate control actions will flood the SOC.
- Ignoring serial DNP3 — the IP network isn't the whole DNP3 footprint.
- Treating SAv5 aggressive mode as "authenticated" — it's the weak mode; monitor accordingly.
- No baseline — DNP3 is deterministic; without a baseline you can't see the deviation.

## References

- IEEE 1815-2012 (DNP3) including Secure Authentication specifications
- NIST SP 800-82 Rev. 3 (Guide to OT Security)
- MITRE ATT&CK for ICS — DNP3-relevant techniques
- NERC CIP standards for applicable electric-sector entities
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
