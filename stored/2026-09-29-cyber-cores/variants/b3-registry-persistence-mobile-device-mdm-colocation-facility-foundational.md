---
skill_id: cyber_b3_registry_persistence_mobile_device_mdm_colocation_facility_foundational
name: Registry Persistence Defense for Mobile Devices (MDM) in Colocation Facilities (Foundational Maturity)
description: "Registry Persistence defense playbook for Mobile Devices (MDM) in Colocation Facilities at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, mobile, mdm, endpoint, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Registry Persistence Defense for Mobile Devices (MDM) in Colocation Facilities (Foundational Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to Mobile Devices (MDM) in Colocation Facilities at Foundational maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in MDM device inventory: OS versions, jailbreak/root detections, installed app lists and Mobile threat defense alerts (malicious apps, network attacks, OS tampering); run `# conceptually (MDM APIs differ):` then `mdm-cli devices list --noncompliant --limit 30`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for Mobile Devices (MDM); Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
