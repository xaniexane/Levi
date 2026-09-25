---
skill_id: cyber_implementing_network_access_control
name: Implementing Network Access Control
description: Deploy 802.1X-based network access control — authentication, authorization, posture assessment, and phased enforcement from monitor to deny.
risk: low
permissions: []
requires_confirmation: false
tags: [network, access-control, 802.1x]
version: 1.0.0
---
## Purpose

Ensure only known, healthy, authorized devices reach the corporate network. Network Access Control combines 802.1X authentication (who/what is connecting), authorization policy (what they may reach), and posture assessment (are they patched, encrypted, EDR-healthy) with enforcement at the switch, wireless controller, or VPN gateway — replacing the flat "plug in and you're trusted" network.

## When to use

- Stopping rogue devices, unauthorized access points, and unknown endpoints from joining the network.
- Meeting compliance requirements for network admission control (PCI DSS 4.0, HIPAA, CMMC).
- Containing compromised or non-compliant endpoints automatically via quarantine VLANs.
- Supporting BYOD and IoT with differentiated access instead of one flat corporate SSID.
- Post-incident, when an attacker device operated undetected on the LAN.

## Prerequisites

- 802.1X-capable switches, wireless controllers, and VPN gateways (verify firmware support; legacy gear may need replacement).
- RADIUS infrastructure (NPS, FreeRADIUS, or a NAC platform's built-in RADIUS) with HA design — authentication is now in the critical path of all connectivity.
- PKI for EAP-TLS certificates (the gold standard) or credential store for PEAP; decide per device class.
- Device inventory and ownership data to build authorization policy (corporate, BYOD, IoT, guest, printer).
- Maintenance windows and a rollback plan: NAC misconfiguration disconnects the business, not just attackers.

## Procedure

1. **Choose the authentication methods per device class.** Corporate managed devices: EAP-TLS with machine certificates (strongest, no passwords). User devices: EAP-TLS with user certs or PEAP with MFA-backed credentials. IoT/printers: MAB (MAC Authentication Bypass) with profiling and locked-down VLANs — MAB is weak authentication, so treat those devices as untrusted by default. Guests: captive portal on an isolated VLAN with client isolation.
2. **Build the RADIUS and policy engine.** Deploy redundant RADIUS servers, integrate with AD/IdP for identity and with MDM/EDR for posture signals. Write authorization policy as explicit rules: corporate-healthy → production VLANs; corporate-noncompliant → remediation VLAN; unknown → deny or guest; IoT profile → IoT VLAN with only required destinations.
3. **Deploy in monitor mode first.** Enable 802.1X with "low-impact"/monitor mode (authenticate but permit regardless of result) across a pilot set of switches. Collect authentication successes, failures, and the long tail of devices that cannot do 802.1X — there will be many (printers, badge readers, lab equipment, OT). This inventory drives the MAB exception list.
4. **Profile and segment the exceptions.** Fingerprint non-802.1X devices (DHCP, CDP/LLDP, HTTP user-agents, MAC OUI) and assign them to restricted segments via MAB with tight ACLs. Every MAB entry gets an owner and a review date; MAB is spoofable, so keep these segments narrow and monitored.
5. **Add posture assessment.** Check patch level, disk encryption, EDR presence/health, and OS version at connect time and periodically. Non-compliant corporate devices go to remediation with access only to update servers; persistent non-compliance escalates to the device owner and, after the grace period, to deny.
6. **Enforce in phases.** Move from monitor to closed/enforcement mode building by building (wired) and SSID by SSID (wireless), with on-site support during each cutover. Keep a tested emergency procedure to drop a switch port back to open mode — during an incident is not the time to discover the rollback is broken.
7. **Cover the VPN and guest paths.** Apply the same policy engine to VPN authentication (posture-check remote devices before granting internal access) and keep guest traffic logically and physically separated with no path to internal resources.
8. **Monitor authentication as a security signal.** Ship RADIUS accept/reject logs to the SIEM. Alert on: repeated EAP failures (password spraying or misconfigured supplicants), MAB devices appearing on new ports (possible spoofing), and authentication from unexpected locations. NAC logs are network-admission telemetry — treat them as detections, not just operations data.

## Expected outputs

- RADIUS infrastructure with HA and documented authentication methods per device class.
- Authorization policy matrix (identity × posture × device class → network segment).
- MAB exception inventory with owners and review dates.
- Phased enforcement record with rollback procedures.
- SIEM detections on authentication anomalies and rogue-device indicators.

## Pitfalls

- **Big-bang enforcement.** Turning on closed mode everywhere on a Friday disconnects printers, badge readers, and the CEO's dock. Phase it, with support staff present.
- **Single RADIUS point of failure.** If RADIUS is down and switches are in closed mode, nobody connects. Deploy HA RADIUS and configure critical-auth (fail-open to a restricted VLAN) deliberately — documenting that you chose availability over security for that path.
- **MAB as "good enough" forever.** MAC addresses are trivially spoofed; MAB exceptions need network-level compensating controls (port security, DHCP snooping, DAI) and should shrink over time, not grow.
- **Forgetting the supplicant.** EAP-TLS requires certificates deployed to devices and supplicants configured; the PKI and MDM rollout is half the project. Plan it as such.
- **No posture re-check.** A device healthy at 9 a.m. can be compromised by noon. Periodic re-authentication and continuous EDR signals matter more than the initial check.

## References

- IEEE 802.1X standard (port-based network access control) — https://standards.ieee.org/
- NIST SP 800-53 Rev. 5, AC-19 / CM-8 and SC-7 boundary protection family — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- MITRE ATT&CK T1133 (External Remote Services) and T1595 (Active Scanning) context — https://attack.mitre.org/
- Vendor 802.1X deployment guides for your switch/wireless platform
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
