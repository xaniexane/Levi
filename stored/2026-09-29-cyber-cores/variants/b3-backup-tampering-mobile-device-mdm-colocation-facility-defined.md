---
skill_id: cyber_b3_backup_tampering_mobile_device_mdm_colocation_facility_defined
name: Backup Tampering Defense for Mobile Devices (MDM) in Colocation Facilities (Defined Maturity)
description: "Backup Tampering defense playbook for Mobile Devices (MDM) in Colocation Facilities at Defined maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, mobile, mdm, endpoint, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# Backup Tampering Defense for Mobile Devices (MDM) in Colocation Facilities (Defined Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Mobile Devices (MDM) in Colocation Facilities at Defined maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in MDM device inventory: OS versions, jailbreak/root detections, installed app lists and Mobile threat defense alerts (malicious apps, network attacks, OS tampering); run `# conceptually (MDM APIs differ):` then `mdm-cli devices list --noncompliant --limit 30`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Mobile Devices (MDM); Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
