---
skill_id: cyber_b3_supply_chain_compromise_macos_endpoint_on_prem_datacenter_defined
name: Supply Chain Compromise Defense for macOS Endpoints in On-Premises Datacenter (Defined Maturity)
description: "Supply Chain Compromise defense playbook for macOS Endpoints in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, malware, macos, endpoint, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# Supply Chain Compromise Defense for macOS Endpoints in On-Premises Datacenter (Defined Maturity)

## Purpose

Trusted software updates or vendor components carry the attacker's payload — the hardest vector to prevent, because the malware arrives signed and expected. Defense shifts to verification, segmentation, and vendor scrutiny. Applies to macOS Endpoints in On-Premises Datacenter at Defined maturity.

## When to use

- A signed, trusted application suddenly exhibiting C2 communication or spawning unexpected children after an update.
- Threat intel or vendor advisory naming a specific product version as compromised.
- Anomalous behavior correlated tightly with a software update timestamp across many hosts.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Identify the trojanized version and enumerate every host that installed it — the exposure list defines the response scope. Then: Determine what the implanted component could access (its privilege level and data reach) to bound the impact.
4. **Contain and harden.** Software allowlisting with version pinning; staged update rollouts with behavioral monitoring before fleet-wide deploy. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming signed = safe; supply-chain malware is signed by definition.
- Delaying response waiting for the vendor's statement while the implant remains active.

## References

- MITRE ATT&CK: T1195 (Initial Access: Supply Chain Compromise)
- Vendor logging and hardening baselines for macOS Endpoints; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
