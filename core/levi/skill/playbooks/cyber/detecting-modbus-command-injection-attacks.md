---
skill_id: cyber_detecting_modbus_command_injection_attacks
name: Detecting Modbus Command Injection Attacks
description: Detect malicious command injection in Modbus/TCP industrial control traffic.
risk: low
permissions: []
requires_confirmation: false
tags: [ics, modbus, detection]
version: 1.0.0
---
## Purpose

Modbus/TCP carries no authentication — any host that can reach a PLC can issue control commands. Command injection (malicious writes to coils/registers, unauthorized function codes) can manipulate physical processes. This playbook helps OT defenders detect malicious Modbus commands using passive network monitoring, baselining, and allowlist-based detection.

## When to use

- You have Modbus/TCP in the OT environment and no detection coverage for it.
- An OT security assessment flagged unauthenticated control protocols.
- Investigating anomalous physical-process behavior with a cyber cause suspected.
- Building an OT SOC use case for industrial protocol abuse.

## Prerequisites

- Passive network visibility into OT segments carrying Modbus/TCP (span/tap on control network; never active scanning of PLCs).
- A protocol-aware monitor: Zeek with ICS protocol support, an OT IDS (e.g., Nozomi, Claroty, Dragos), or Modbus-parsing packet capture.
- Asset inventory: which PLCs/RTUs speak Modbus, their unit IDs, and normal master (HMI/SCADA) sources.
- Change-management records for legitimate logic/setpoint changes.

## Procedure

1. Map legitimate Modbus masters first. Identify every authorized Modbus client (HMIs, SCADA servers, historians) and the PLCs each may address. In a healthy OT network this set is small and static — any new master is immediately suspicious. Document it as an allowlist, not a mental model.
2. Baseline function-code usage per master/slave pair. Record which function codes each master legitimately uses (e.g., read holding registers 0x03 vs. write single coil 0x05, write multiple registers 0x10). Attackers injecting commands typically use write function codes or diagnostics (0x08) that the HMI never sends — function-code anomalies are high-fidelity alerts.
3. Alert on write operations from unauthorized sources. Any Modbus write (coils, registers) originating from a host not on the master allowlist is the primary detection. Also alert on writes to safety-critical addresses outside maintenance windows, and on broadcast or unusual unit-ID targeting.
4. Detect reconnaissance precursors. Function-code scans, sequential unit-ID enumeration, and read-all-register sweeps from non-engineering hosts typically precede injection. Correlate: recon from a host followed by writes from the same host is an attack sequence, not two alerts.
5. Validate against process context before acting. A write during a planned maintenance window by an engineering workstation may be legitimate — check change records. A write at 3 AM from a host in the corporate DMZ is not. Never take disruptive action on OT alerts without operations involvement.
6. Respond with OT-appropriate containment. Isolate the offending host at the network boundary (OT firewall), preserve packet captures and device logs, engage process engineers to verify physical process integrity, and review PLC logic for unauthorized changes. Do not reboot or reflash controllers without vendor/engineering guidance.

## Expected outputs

- Master allowlist: authorized Modbus clients per PLC/unit ID.
- Function-code baselines per master/slave pair with anomaly alerts.
- Detection rules: unauthorized writes, off-window safety writes, recon precursors.
- OT incident response contacts and escalation path (IT + operations + vendor).

## Pitfalls

- Active scanning of PLCs can crash them — this playbook is passive monitoring only.
- Modbus has no authentication, so 'authenticated session' logic doesn't apply — rely on source allowlisting.
- Engineering workstations legitimately issue writes during maintenance — integrate change windows or drown in false positives.
- IT-style containment (reimage the host) doesn't apply to controllers — involve OT engineers before touching devices.
- Encrypted tunnels (VPNs) into OT hide Modbus from passive monitors — ensure monitoring points see decrypted traffic.

## References

- NIST SP 800-82 Rev. 3 (OT security); MITRE ATT&CK for ICS: T855 (Modify Controller Tasking), T0807 (Command-Line Interface via ICS) — https://attack.mitre.org/techniques/ics/; Modbus protocol specification (modbus.org)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
