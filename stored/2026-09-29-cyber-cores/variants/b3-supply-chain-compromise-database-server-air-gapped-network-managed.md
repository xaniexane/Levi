---
skill_id: cyber_b3_supply_chain_compromise_database_server_air_gapped_network_managed
name: Supply Chain Compromise Defense for Database Servers in Air-Gapped Networks (Managed Maturity)
description: "Supply Chain Compromise defense playbook for Database Servers in Air-Gapped Networks at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, malware, data, database, air-gap, ot, high-security, maturity-managed]
version: 1.0.0
---
# Supply Chain Compromise Defense for Database Servers in Air-Gapped Networks (Managed Maturity)

## Purpose

Trusted software updates or vendor components carry the attacker's payload — the hardest vector to prevent, because the malware arrives signed and expected. Defense shifts to verification, segmentation, and vendor scrutiny. Applies to Database Servers in Air-Gapped Networks at Managed maturity.

## When to use

- A signed, trusted application suddenly exhibiting C2 communication or spawning unexpected children after an update.
- Threat intel or vendor advisory naming a specific product version as compromised.
- Anomalous behavior correlated tightly with a software update timestamp across many hosts.
- Lens: Best telemetry: query audit logs (who ran what) + auth logs + backup/restore history. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Database audit log: logons, privileged statements (DCL/DDL), and bulk-export queries and Slow/general query logs around the incident window; new users, roles, or linked servers; run `-- PostgreSQL style:` then `SELECT usename, query, query_start FROM pg_stat_activity WHERE state='active' ORDER BY query_start;`.
3. **Analyze.** Identify the trojanized version and enumerate every host that installed it — the exposure list defines the response scope. Then: Determine what the implanted component could access (its privilege level and data reach) to bound the impact.
4. **Contain and harden.** Software allowlisting with version pinning; staged update rollouts with behavioral monitoring before fleet-wide deploy. Asset layer: Least-privilege DB roles, no app superusers, encrypted connections, auditing on privileged actions. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming signed = safe; supply-chain malware is signed by definition.
- Delaying response waiting for the vendor's statement while the implant remains active.

## References

- MITRE ATT&CK: T1195 (Initial Access: Supply Chain Compromise)
- Vendor logging and hardening baselines for Database Servers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
