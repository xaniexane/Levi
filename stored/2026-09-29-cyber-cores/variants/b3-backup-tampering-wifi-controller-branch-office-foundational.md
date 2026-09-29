---
skill_id: cyber_b3_backup_tampering_wifi_controller_branch_office_foundational
name: Backup Tampering Defense for Wireless Controllers in Branch Offices (Foundational Maturity)
description: "Backup Tampering defense playbook for Wireless Controllers in Branch Offices at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, network, wireless, branch, maturity-foundational]
version: 1.0.0
---
# Backup Tampering Defense for Wireless Controllers in Branch Offices (Foundational Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Wireless Controllers in Branch Offices at Foundational maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Client association, authentication (EAP) and roaming logs with device MACs and Rogue AP / evil-twin detections and deauth-flood alerts from WIDS; run `# conceptually (vendor CLIs differ):` then `show wireless client summary | include <suspect-mac>`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Wireless Controllers; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
