---
skill_id: cyber_b3_supply_chain_compromise_wifi_controller_on_prem_datacenter_managed
name: Supply Chain Compromise Defense for Wireless Controllers in On-Premises Datacenter (Managed Maturity)
description: "Supply Chain Compromise defense playbook for Wireless Controllers in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, malware, network, wireless, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Supply Chain Compromise Defense for Wireless Controllers in On-Premises Datacenter (Managed Maturity)

## Purpose

Trusted software updates or vendor components carry the attacker's payload — the hardest vector to prevent, because the malware arrives signed and expected. Defense shifts to verification, segmentation, and vendor scrutiny. Applies to Wireless Controllers in On-Premises Datacenter at Managed maturity.

## When to use

- A signed, trusted application suddenly exhibiting C2 communication or spawning unexpected children after an update.
- Threat intel or vendor advisory naming a specific product version as compromised.
- Anomalous behavior correlated tightly with a software update timestamp across many hosts.
- Lens: Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Client association, authentication (EAP) and roaming logs with device MACs and Rogue AP / evil-twin detections and deauth-flood alerts from WIDS; run `# conceptually (vendor CLIs differ):` then `show wireless client summary | include <suspect-mac>`.
3. **Analyze.** Identify the trojanized version and enumerate every host that installed it — the exposure list defines the response scope. Then: Determine what the implanted component could access (its privilege level and data reach) to bound the impact.
4. **Contain and harden.** Software allowlisting with version pinning; staged update rollouts with behavioral monitoring before fleet-wide deploy. Asset layer: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming signed = safe; supply-chain malware is signed by definition.
- Delaying response waiting for the vendor's statement while the implant remains active.

## References

- MITRE ATT&CK: T1195 (Initial Access: Supply Chain Compromise)
- Vendor logging and hardening baselines for Wireless Controllers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
