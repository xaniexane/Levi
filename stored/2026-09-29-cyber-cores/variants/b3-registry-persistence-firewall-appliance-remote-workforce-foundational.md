---
skill_id: cyber_b3_registry_persistence_firewall_appliance_remote_workforce_foundational
name: Registry Persistence Defense for Firewall Appliances in Remote Workforce (Foundational Maturity)
description: "Registry Persistence defense playbook for Firewall Appliances in Remote Workforce at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, network, firewall, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Registry Persistence Defense for Firewall Appliances in Remote Workforce (Foundational Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to Firewall Appliances in Remote Workforce at Foundational maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log and Configuration revisions and diffs; VPN session logs and authentication failures; run `# vendor CLIs differ; conceptually:` then `show log traffic query (source <suspect-ip>)             # Palo Alto style`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for Firewall Appliances; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
