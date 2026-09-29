---
skill_id: cyber_b3_kerberoasting_network_switch_on_prem_datacenter_foundational
name: Kerberoasting Defense for Network Switches in On-Premises Datacenter (Foundational Maturity)
description: "Kerberoasting defense playbook for Network Switches in On-Premises Datacenter at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, network, switching, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# Kerberoasting Defense for Network Switches in On-Premises Datacenter (Foundational Maturity)

## Purpose

Attackers request service tickets for SPN accounts and crack them offline to recover service-account passwords — no alerts on the DC, because requesting tickets is normal. The defense is making those passwords uncrackable and the requests visible. Applies to Network Switches in On-Premises Datacenter at Foundational maturity.

## When to use

- A single account requesting an unusual number of service tickets (4769) with RC4 encryption for many different SPNs in a short window.
- Ticket requests for SPNs from accounts with no business need, or requests at odd hours from a workstation (not a server).
- Subsequent use of a cracked service account: logons from unexpected hosts or privilege changes for that account.
- Lens: Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Syslog: link-state changes, MAC flaps, STP topology changes, login attempts and MAC address tables and ARP tables for device-to-port mapping during incidents; run `show mac address-table | include <suspect-mac>` then `show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY`.
3. **Analyze.** List every SPN targeted and assess the crackability of each service account's password (length, complexity, age). Then: If a service account was cracked, treat it as full compromise: inventory everything that account could touch.
4. **Contain and harden.** Service accounts: 25+ character random passwords, or better, group Managed Service Accounts (gMSA) with automatic rotation. Asset layer: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the password but leaving the SPN on a weak account — the attacker just roasts it again.
- Missing that the cracked service account may have been used to request MORE tickets (roast chaining).

## References

- MITRE ATT&CK: T1558.003 (Credential Access: Kerberoasting)
- Vendor logging and hardening baselines for Network Switches; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
