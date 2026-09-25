---
skill_id: cyber_detecting_bluetooth_low_energy_attacks
name: Detecting Bluetooth Low Energy Attacks
description: Detect BLE attacks — spoofing, MitM, and malicious peripherals — with RF monitoring and host telemetry.
risk: info
permissions: []
requires_confirmation: false
tags: [wireless, bluetooth, detection]
version: 1.0.0
---
## Purpose

Detect attacks against Bluetooth Low Energy: malicious peripherals, man-in-the-middle on pairing, and BLE-based proximity attacks — the wireless attack surface most organizations never monitor. Defensive detection for the RF layer everyone forgets.

## When to use

- Securing environments with BLE-dependent systems (medical devices, industrial sensors, smart locks, point-of-sale).
- Investigating suspected proximity-based attacks or rogue-device activity.
- Auditing BLE device deployments for spoofing and impersonation risk.
- Red-team/blue-team exercises covering the wireless attack surface.

## Prerequisites

- BLE sniffing capability (Ubertooth, nRF sniffer, or software-defined radio with BLE support) for the area being monitored.
- Inventory of legitimate BLE devices: MAC addresses (noting randomization), advertised names, and expected locations.
- Host logs for BLE pairing events (Windows, macOS, Linux bluetoothd logs) centralized where possible.
- Physical access to the monitored area for sensor placement.

## Procedure

1. **Baseline the legitimate BLE landscape.** Survey the area: record advertised device names, MAC addresses, signal strengths, and advertisement intervals for legitimate devices. Note which devices use MAC randomization (most modern phones/OSes do) — your baseline must handle rotating addresses or every phone becomes an alert.
2. **Monitor for spoofed and impersonating devices.** Alert on: duplicate advertised names with different MACs, devices advertising as trusted peripherals (keyboards, headsets) that weren't in the baseline, and signal-strength anomalies (a "nearby" trusted device with an impossibly weak or strong signal suggests a remote impersonator).
3. **Detect pairing and connection attacks.** Monitor host Bluetooth logs for: unexpected pairing requests, pairing with devices not in the baseline, repeated pairing failures (brute-force on legacy pairing), and connections using "Just Works" pairing for sensitive device classes. Alert on any pairing event involving a device flagged in step 2.
4. **Watch for BLE MitM indicators.** Flag: devices advertising with manipulated connection parameters, unexpected GATT service changes on known devices, and man-in-the-middle signatures like relayed advertisements with timing anomalies. Tools that detect BTLEJack-style interception patterns belong in the monitoring toolkit for high-security areas.
5. **Hunt malicious peripherals.** BLE attack tools often present as innocuous devices. Periodically sweep with a sniffer for: devices with no legitimate business purpose in the area, devices that appear only during sensitive meetings or operations, and devices exhibiting attack-tool advertisement fingerprints (unusual intervals, specific payload patterns).
6. **Correlate with physical security.** Join BLE anomalies with badge-access logs and camera coverage where available: a spoofed keyboard appearing in a conference room during an executive meeting is a different priority than one in a lab. Time-box investigations to the anomaly window.
7. **Respond by locating and removing.** On confirmed malicious device: use signal-strength triangulation from multiple sniffer positions to physically locate it, involve physical security for retrieval, and preserve it for forensics. Review host logs for any successful pairings with the device during its presence window — those hosts need investigation.

## Expected outputs

- A baselined BLE device inventory with spoofing and impersonation monitoring.
- Host pairing-event alerting correlated with sniffer observations.
- Periodic malicious-peripheral sweeps and a locate-and-remove response procedure.

## Pitfalls

- No baseline — every visitor's phone is an "unknown device" and the monitoring is useless.
- Ignoring MAC randomization — modern devices rotate addresses; identity must come from advertisement content and behavior, not MAC alone.
- Monitoring without physical response capability — detecting a rogue device you can't locate or remove is just awareness of your compromise.
- Forgetting that BLE range extends through walls — the attacker doesn't need to be in the room.
- No host-log correlation — the sniffer sees the air; only host logs show successful pairing.

## References

- Bluetooth SIG — BLE security documentation (pairing modes, LE Secure Connections)
- NIST SP 800-121 Rev. 2 (Guide to Bluetooth Security)
- MITRE ATT&CK T1557 (Adversary-in-the-Middle) in wireless context
- Ubertooth / nRF sniffer documentation for BLE capture
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
