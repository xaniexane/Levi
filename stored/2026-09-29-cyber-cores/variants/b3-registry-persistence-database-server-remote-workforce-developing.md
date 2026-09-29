---
skill_id: cyber_b3_registry_persistence_database_server_remote_workforce_developing
name: Registry Persistence Defense for Database Servers in Remote Workforce (Developing Maturity)
description: "Registry Persistence defense playbook for Database Servers in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, data, database, remote, endpoint, zero-trust, maturity-developing]
version: 1.0.0
---
# Registry Persistence Defense for Database Servers in Remote Workforce (Developing Maturity)

## Purpose

Run keys, services, Winlogon helpers, and COM hijacks give attackers reboot-surviving execution with minimal footprint. Baseline the autoruns on gold images; alert on deviations, not on the mechanism's existence. Applies to Database Servers in Remote Workforce at Developing maturity.

## When to use

- Writes to Run/RunOnce keys, Winlogon Userinit/Shell values, or service ImagePath entries pointing at unusual binaries.
- Sysmon event 13 (registry value set) on autorun locations by non-installer processes, or new services with suspicious binaries.
- Autoruns deltas: new entries appearing between baseline scans on hosts with no software-change record.
- Lens: Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries and Slow/general query logs around the incident window; new users, roles, or linked servers; run `-- PostgreSQL style:` then `SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;`.
3. **Analyze.** Capture the referenced binary: hash, signature, and sandbox detonation to confirm malicious intent. Then: Check the same autorun locations across the fleet — registry persistence is often deployed identically to many hosts.
4. **Contain and harden.** Scheduled Autoruns/Sysmon baselining with alerting on new persistence entries; restrict registry write rights for standard users. Asset layer: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the registry value while the dropper that restores it still runs on a schedule.
- Overlooking user-hive (HKCU) persistence during a 'system-only' triage.

## References

- MITRE ATT&CK: T1112 (Defense Evasion: Modify Registry) for persistence
- Vendor logging and hardening baselines for Database Servers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
