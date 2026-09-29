---
skill_id: cyber_b3_session_hijacking_backup_server_on_prem_datacenter_foundational
name: Web Session Hijacking Defense for Backup Servers in On-Premises Datacenter (Foundational Maturity)
description: "Web Session Hijacking defense playbook for Backup Servers in On-Premises Datacenter at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, backup, ransomware, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# Web Session Hijacking Defense for Backup Servers in On-Premises Datacenter (Foundational Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to Backup Servers in On-Premises Datacenter at Foundational maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: job audit logs + admin-console access logs + integrity-check results. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Backup job definitions, run histories, and deletion/retention-change audit entries and Admin console logons and configuration exports; repository credential-change history; run `# conceptually (product CLIs differ):` then `backup-cli jobs list --failed --last 7d`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: Immutable storage, separate admin credentials with MFA, no domain-joined backup console if avoidable. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for Backup Servers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
