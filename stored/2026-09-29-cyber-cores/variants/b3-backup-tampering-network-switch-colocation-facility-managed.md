---
skill_id: cyber_b3_backup_tampering_network_switch_colocation_facility_managed
name: Backup Tampering Defense for Network Switches in Colocation Facilities (Managed Maturity)
description: "Backup Tampering defense playbook for Network Switches in Colocation Facilities at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, network, switching, on-prem, colocation, maturity-managed]
version: 1.0.0
---
# Backup Tampering Defense for Network Switches in Colocation Facilities (Managed Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to Network Switches in Colocation Facilities at Managed maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Syslog: link-state changes, MAC flaps, STP topology changes, login attempts and MAC address tables and ARP tables for device-to-port mapping during incidents; run `show mac address-table | include <suspect-mac>` then `show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for Network Switches; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
