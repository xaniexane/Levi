---
skill_id: cyber_detecting_modbus_protocol_anomalies
name: Detecting Modbus Protocol Anomalies
description: Baseline Modbus/TCP traffic and alert on protocol-level anomalies in OT networks.
risk: low
permissions: []
requires_confirmation: false
tags: [ics, modbus, anomaly-detection]
version: 1.0.0
---
## Purpose

Beyond outright command injection, subtler Modbus anomalies — malformed packets, timing deviations, unexpected slaves, protocol tunneling — can indicate reconnaissance, tooling, or process manipulation. This playbook builds a protocol-anomaly detection capability: baselining what 'normal Modbus' looks like and alerting on deviations at the protocol layer.

## When to use

- Modbus command-injection detection exists but you need deeper protocol-layer coverage.
- Threat hunting in OT for low-and-slow manipulation.
- An OT IDS deployment needs tuning for your specific Modbus environment.
- Investigating intermittent process anomalies with no clear mechanical cause.

## Prerequisites

- Passive Modbus/TCP visibility (span/tap) with full packet capture or protocol-parsed logs.
- A Modbus-aware parser (Zeek ICS scripts, OT IDS, or tshark/Wireshark dissectors) producing structured fields: transaction ID, unit ID, function code, addresses, values.
- Baseline capture period covering normal operations including shift changes and batch cycles.
- Asset inventory of Modbus slaves (unit IDs, IP addresses, device roles).

## Procedure

1. Build a protocol baseline, not just a traffic baseline. For each master/slave pair record: function codes used, register/coil address ranges accessed, typical values and value ranges, polling intervals and jitter, and transaction-ID sequencing behavior. OT traffic is highly periodic — that determinism is your detection advantage.
2. Alert on structural anomalies. Flag: malformed Modbus frames (bad length fields, truncated packets), function codes never seen in baseline, requests to unmapped unit IDs or non-existent slaves, transaction-ID patterns inconsistent with the master's stack (some stacks increment predictably — randomization suggests a different tool), and Modbus on non-standard ports (tunneling or rogue devices).
3. Alert on timing and volume anomalies. Flag: polling-interval deviations beyond normal jitter, burst reads across full address ranges (reconnaissance sweeps), new masters appearing, and slaves that go silent (possible device impersonation or failure — both matter). Correlate timing anomalies with physical-process data where available.
4. Detect device spoofing and MITM indicators. Watch for: duplicate IP/MAC claiming to be a known slave, ARP anomalies around Modbus devices, response-time changes suggesting an intermediary, and inconsistent device fingerprinting (function-code support differing from the known device profile).
5. Tune with operations in the loop. Every anomaly needs an OT-validity check: firmware updates, new recipes, and seasonal production changes all alter Modbus patterns legitimately. Maintain a change log feed into the SOC and require operations sign-off before treating a novel pattern as malicious.
6. Document and escalate per OT severity. Protocol anomalies map to process risk: reconnaissance (monitor and hunt), unauthorized writes (incident), device impersonation (safety-critical incident). Define these tiers with operations beforehand — not during an event.

## Expected outputs

- Modbus protocol baseline: per-pair function codes, address ranges, timing, sequencing.
- Anomaly detection rules: structural, timing/volume, spoofing/MITM indicators.
- OT change-feed integration so legitimate changes don't generate incidents.
- Severity tiers agreed with operations, with escalation contacts.

## Pitfalls

- OT networks are deterministic until they aren't — recipe changes and maintenance alter baselines; integrate change data.
- Encrypted or tunneled Modbus defeats passive parsing — monitor at points where traffic is plaintext.
- Alerting on every malformed packet fires on flaky serial-to-Ethernet gateways — distinguish device faults from attacks.
- Transaction-ID analysis is stack-specific; validate the pattern per master before alerting on deviations.
- Never run active probes to 'test' anomaly hypotheses against live PLCs.

## References

- NIST SP 800-82 Rev. 3 (OT security); MITRE ATT&CK for ICS: T0884 (Connection Proxy), T0809 (Data Destruction via ICS) — https://attack.mitre.org/ (ICS matrix); Zeek ICS protocol documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
