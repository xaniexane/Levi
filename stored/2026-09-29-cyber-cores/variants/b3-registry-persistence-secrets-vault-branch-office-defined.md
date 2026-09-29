---
skill_id: cyber_b3_registry_persistence_secrets_vault_branch_office_defined
name: Registry Persistence Defense for Secrets Vaults in Branch Offices (Defined Maturity)
description: "Registry Persistence defense playbook for Secrets Vaults in Branch Offices at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, secrets, identity, branch, network, maturity-defined]
version: 1.0.0
---
# Registry Persistence Defense for Secrets Vaults in Branch Offices (Defined Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to Secrets Vaults in Branch Offices at Defined maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Audit log of secret reads/writes/deletes with client identity and source IP and Policy and auth-method changes; root-token generation events; run `vault audit log --since 24h 2>/dev/null | grep -E '"path":"secret' | head -20` then `vault list sys/policy 2>/dev/null; vault auth list 2>/dev/null`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for Secrets Vaults; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
