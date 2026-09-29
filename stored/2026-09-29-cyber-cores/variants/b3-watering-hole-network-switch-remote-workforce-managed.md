---
skill_id: cyber_b3_watering_hole_network_switch_remote_workforce_managed
name: Watering Hole Attack Defense for Network Switches in Remote Workforce (Managed Maturity)
description: "Watering Hole Attack defense playbook for Network Switches in Remote Workforce at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, switching, remote, endpoint, zero-trust, maturity-managed]
version: 1.0.0
---
# Watering Hole Attack Defense for Network Switches in Remote Workforce (Managed Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to Network Switches in Remote Workforce at Managed maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Syslog: link-state changes, MAC flaps, STP topology changes, login attempts and MAC address tables and ARP tables for device-to-port mapping during incidents; run `show mac address-table | include <suspect-mac>` then `show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for Network Switches; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
