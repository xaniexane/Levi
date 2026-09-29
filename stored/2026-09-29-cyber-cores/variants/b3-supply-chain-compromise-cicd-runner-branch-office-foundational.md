---
skill_id: cyber_b3_supply_chain_compromise_cicd_runner_branch_office_foundational
name: Supply Chain Compromise Defense for CI/CD Runners in Branch Offices (Foundational Maturity)
description: "Supply Chain Compromise defense playbook for CI/CD Runners in Branch Offices at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, malware, devops, branch, network, maturity-foundational]
version: 1.0.0
---
# Supply Chain Compromise Defense for CI/CD Runners in Branch Offices (Foundational Maturity)

## Purpose

Trusted software updates or vendor components carry the attacker's payload — the hardest vector to prevent, because the malware arrives signed and expected. Defense shifts to verification, segmentation, and vendor scrutiny. Applies to CI/CD Runners in Branch Offices at Foundational maturity.

## When to use

- A signed, trusted application suddenly exhibiting C2 communication or spawning unexpected children after an update.
- Threat intel or vendor advisory naming a specific product version as compromised.
- Anomalous behavior correlated tightly with a software update timestamp across many hosts.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Identify the trojanized version and enumerate every host that installed it — the exposure list defines the response scope. Then: Determine what the implanted component could access (its privilege level and data reach) to bound the impact.
4. **Contain and harden.** Software allowlisting with version pinning; staged update rollouts with behavioral monitoring before fleet-wide deploy. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming signed = safe; supply-chain malware is signed by definition.
- Delaying response waiting for the vendor's statement while the implant remains active.

## References

- MITRE ATT&CK: T1195 (Initial Access: Supply Chain Compromise)
- Vendor logging and hardening baselines for CI/CD Runners; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
