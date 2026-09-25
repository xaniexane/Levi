---
skill_id: cyber_conducting_man_in_the_middle_attack_simulation
name: Authorized Man-in-the-Middle Testing and ARP Spoofing Detection
description: Defensive playbook for running authorized MITM resilience tests and detecting ARP spoofing and interception on your networks.
risk: low
permissions: []
requires_confirmation: false
tags: [network, detection, assessment]
version: 1.0.0
---
## Purpose
Man-in-the-middle attacks intercept traffic via ARP spoofing, rogue DHCP, or compromised network devices. Defenders need both sides: the ability to run authorized MITM simulations that validate encryption and detection controls, and the monitoring to catch real interception attempts. This playbook covers both, with no offensive tradecraft.

## When to use
- Validating that sensitive applications resist interception (HSTS, certificate pinning).
- Testing whether network monitoring detects ARP spoofing.
- Investigating alerts about duplicate MAC addresses or gateway impersonation.
- Hardening networks where interception would have high impact.

## Prerequisites
- Written authorization for any active simulation, with defined network segments.
- Network monitoring: ARP tables, DHCP logs, and ideally dynamic ARP inspection.
- Inventory of sensitive applications and their TLS configurations.
- Containment capability for rogue devices.

## Procedure
1. Authorize and scope the simulation. Document the segments, techniques to be simulated, and time window; get written approval.
2. Establish detection baselines. Record normal ARP behavior, gateway MAC addresses, and DHCP server identities before testing.
3. Run controlled simulations. Within scope, simulate ARP spoofing or rogue DHCP to test whether monitoring detects and alerts; stop immediately on unexpected impact.
4. Validate application resilience. Confirm sensitive apps enforce TLS, HSTS, and certificate validation so intercepted traffic remains unreadable and unmodifiable.
5. Build production detections. Alert on gratuitous ARP anomalies, MAC flapping, duplicate IP-to-MAC mappings, and unauthorized DHCP servers.
6. Enable switch-level protections. Deploy dynamic ARP inspection, DHCP snooping, and port security on managed switches.
7. Investigate real alerts. For suspected live interception, identify the rogue device, isolate it, and determine what traffic was exposed.
8. Review and harden. Close gaps found in the simulation: missing TLS enforcement, unmonitored segments, or unmanaged switches.

## Expected outputs
- Simulation report with detection gaps and application resilience findings.
- ARP/DHCP anomaly detections in production monitoring.
- Switch hardening (DAI, DHCP snooping) deployment status.

## Pitfalls
- Simulating interception on production networks without authorization is indistinguishable from an attack.
- Relying on encryption alone while ignoring detection; defense in depth needs both.
- Unmanaged switches and IoT segments where spoofing protections cannot be enforced.
- Alerting on ARP anomalies without baselines produces noise.

## References
- MITRE ATT&CK: T1557 (Adversary-in-the-Middle)
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- Vendor documentation for dynamic ARP inspection and DHCP snooping
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
