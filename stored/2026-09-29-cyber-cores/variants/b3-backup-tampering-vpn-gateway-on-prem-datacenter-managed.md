---
skill_id: cyber_b3_backup_tampering_vpn_gateway_on_prem_datacenter_managed
name: Backup Tampering Defense for VPN Gateways in On-Premises Datacenter (Managed Maturity)
description: "Backup Tampering defense playbook for VPN Gateways in On-Premises Datacenter at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, network, vpn, remote-access, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Backup Tampering Defense for VPN Gateways in On-Premises Datacenter (Managed Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to VPN Gateways in On-Premises Datacenter at Managed maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in VPN auth logs (success/failure per user with source IPs), session tables with data volumes and Gateway admin audit log and firmware/patch version; client version inventory; run `# conceptually (vendor CLIs differ):` then `show vpn-sessiondb detail anyconnect | grep -E 'Username|Assigned IP|Login Time'`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for VPN Gateways; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
