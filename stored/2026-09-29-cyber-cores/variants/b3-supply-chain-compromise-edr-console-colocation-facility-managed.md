---
skill_id: cyber_b3_supply_chain_compromise_edr_console_colocation_facility_managed
name: Supply Chain Compromise Defense for EDR Consoles in Colocation Facilities (Managed Maturity)
description: "Supply Chain Compromise defense playbook for EDR Consoles in Colocation Facilities at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, malware, soc, edr, endpoint, on-prem, colocation, maturity-managed]
version: 1.0.0
---
# Supply Chain Compromise Defense for EDR Consoles in Colocation Facilities (Managed Maturity)

## Purpose

Trusted software updates or vendor components carry the attacker's payload — the hardest vector to prevent, because the malware arrives signed and expected. Defense shifts to verification, segmentation, and vendor scrutiny. Applies to EDR Consoles in Colocation Facilities at Managed maturity.

## When to use

- A signed, trusted application suddenly exhibiting C2 communication or spawning unexpected children after an update.
- Threat intel or vendor advisory naming a specific product version as compromised.
- Anomalous behavior correlated tightly with a software update timestamp across many hosts.
- Lens: Best telemetry: raw process/network telemetry + detection history + sensor health inventory. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Full process trees with command lines, hashes, and network connections for suspect hosts and Detection and response action history (isolations, kills, quarantines); run `# conceptually (EDR APIs differ):` then `edr-cli hunt process --hostname <host> --since 24h --tree`.
3. **Analyze.** Identify the trojanized version and enumerate every host that installed it — the exposure list defines the response scope. Then: Determine what the implanted component could access (its privilege level and data reach) to bound the impact.
4. **Contain and harden.** Software allowlisting with version pinning; staged update rollouts with behavioral monitoring before fleet-wide deploy. Asset layer: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming signed = safe; supply-chain malware is signed by definition.
- Delaying response waiting for the vendor's statement while the implant remains active.

## References

- MITRE ATT&CK: T1195 (Initial Access: Supply Chain Compromise)
- Vendor logging and hardening baselines for EDR Consoles; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
