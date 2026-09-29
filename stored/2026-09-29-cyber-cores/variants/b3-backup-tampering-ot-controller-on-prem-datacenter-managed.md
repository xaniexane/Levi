---
skill_id: cyber_b3_backup_tampering_ot_controller_on_prem_datacenter_managed
name: Backup Tampering Defense for OT Controllers in On-Premises Datacenter (Managed Maturity)
description: "Backup Tampering defense playbook for OT Controllers in On-Premises Datacenter at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, ot, ics, critical-infrastructure, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Backup Tampering Defense for OT Controllers in On-Premises Datacenter (Managed Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to OT Controllers in On-Premises Datacenter at Managed maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for OT Controllers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
