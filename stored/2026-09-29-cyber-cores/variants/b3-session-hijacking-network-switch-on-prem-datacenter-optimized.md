---
skill_id: cyber_b3_session_hijacking_network_switch_on_prem_datacenter_optimized
name: Web Session Hijacking Defense for Network Switches in On-Premises Datacenter (Optimized Maturity)
description: "Web Session Hijacking defense playbook for Network Switches in On-Premises Datacenter at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, network, switching, on-prem, datacenter, maturity-optimized]
version: 1.0.0
---
# Web Session Hijacking Defense for Network Switches in On-Premises Datacenter (Optimized Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to Network Switches in On-Premises Datacenter at Optimized maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Syslog: link-state changes, MAC flaps, STP topology changes, login attempts and MAC address tables and ARP tables for device-to-port mapping during incidents; run `show mac address-table | include <suspect-mac>` then `show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for Network Switches; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
