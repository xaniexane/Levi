---
skill_id: cyber_b3_dll_hijacking_database_server_on_prem_datacenter_foundational
name: DLL Hijacking Defense for Database Servers in On-Premises Datacenter (Foundational Maturity)
description: "DLL Hijacking defense playbook for Database Servers in On-Premises Datacenter at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, data, database, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# DLL Hijacking Defense for Database Servers in On-Premises Datacenter (Foundational Maturity)

## Purpose

Applications loading DLLs from insecure paths let attackers plant a malicious DLL that executes with the application's privileges. Detection focuses on DLL loads from writable directories and known-vulnerable applications. Applies to Database Servers in On-Premises Datacenter at Foundational maturity.

## When to use

- Sysmon event 7 (image loaded) showing DLLs loaded from temp, downloads, or user-writable directories by privileged processes.
- New DLL files appearing alongside application executables, especially with names matching system DLLs.
- Application crashes or behavior changes after a DLL appears in its directory.
- Lens: Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries and Slow/general query logs around the incident window; new users, roles, or linked servers; run `-- PostgreSQL style:` then `SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;`.
3. **Analyze.** Verify the loading order: confirm the planted DLL shadows a legitimate one via PATH or application-directory precedence. Then: Check the DLL's exports and behavior in a sandbox — many hijack DLLs proxy the original to stay stealthy.
4. **Contain and harden.** Applications should use absolute paths and SafeDllSearchMode; remove user-writable directories from the DLL search order. Asset layer: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the DLL without fixing the insecure load order — the hole remains for the next attacker.
- Assuming signed applications are immune; the signature covers the EXE, not the DLL it loads.

## References

- MITRE ATT&CK: T1574.001 (Persistence: DLL Search Order Hijacking)
- Vendor logging and hardening baselines for Database Servers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
