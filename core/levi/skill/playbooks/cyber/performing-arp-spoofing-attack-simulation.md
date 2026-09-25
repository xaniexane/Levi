---
skill_id: cyber_performing_arp_spoofing_attack_simulation
name: ARP Spoofing Simulation for Detection Engineering (Defensive)
description: Simulate ARP spoofing in an isolated lab to build and validate network detections.
risk: low
permissions: []
requires_confirmation: false
tags: [network-security, detection-engineering, lab-testing]
version: 1.0.0
---

## Purpose
ARP spoofing enables man-in-the-middle attacks on local networks. This playbook uses controlled lab simulation of ARP spoofing solely to develop, tune, and validate detections and hardening — never against production networks or systems you do not own.

## When to use
- Building SIEM/NDR detections for layer-2 attacks.
- Validating that Dynamic ARP Inspection (DAI) and related controls actually work.
- Training analysts to recognize MITM indicators in network telemetry.

## Prerequisites
- An isolated lab network (virtual or physical) with no path to production.
- Packet capture capability (Wireshark/tcpdump) and a SIEM/NDR instance receiving lab telemetry.
- Switch with DAI/DHCP-snooping configurability for control-validation phases.

## Procedure
1. **Build the isolated lab.** Two victim VMs, an attacker VM, and a span/mirror port feeding capture; verify isolation from production networks.
2. **Baseline normal ARP.** Capture legitimate ARP traffic: request/reply rates, gratuitous ARPs, and MAC-to-IP stability over time.
3. **Simulate the spoof.** From the lab attacker, send gratuitous ARP replies mapping the gateway IP to the attacker MAC; observe victim traffic redirection in the capture.
4. **Develop detections.** From the capture, build rules for: gratuitous ARP storms, MAC flapping (one IP claimed by multiple MACs), ARP replies without preceding requests, and gateway MAC changes.
5. **Validate controls.** Enable DAI with DHCP snooping on the lab switch; re-run the simulation and confirm the attack is blocked and logged.
6. **Export detection content.** Package the validated rules (Sigma, Snort/Suricata, SIEM queries) with the lab evidence that proves they fire.
7. **Tear down cleanly.** Document results, archive captures per retention policy, and confirm no simulation artifacts or tooling remain outside the lab.

8. **Test detection resilience.** Vary the simulation (timing, packet rates, targeted hosts) to ensure detections catch the behavior class, not one specific packet pattern.
9. **Extend to IPv6.** Repeat the exercise for IPv6 neighbor spoofing (rogue router advertisements); the attack class survives the protocol transition.

## Expected outputs
- Validated ARP-spoofing detections with lab evidence of true and false positive behavior.
- Control validation report for DAI/DHCP snooping configurations.
- Hardening recommendations for production access-layer switches.
- Example: the lab simulation produces a MAC-flap alert within 30 seconds of spoofing start; after enabling DAI, the same simulation is blocked at the switch and logged, with no victim impact.

## Pitfalls
- Running spoofing tools anywhere near production: even "accidental" lab leakage disrupts real networks.
- Detections tuned only to the lab's exact packet pattern; generalize to behavior, not bytes.
- Declaring the network safe because DAI is "enabled" without ever testing it.

## References
- MITRE ATT&CK T1557 (Adversary-in-the-Middle).
- NIST SP 800-94, Guide to Intrusion Detection and Prevention Systems.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
