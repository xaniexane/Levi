---
skill_id: cyber_b3_session_hijacking_windows_server_air_gapped_network_foundational
name: Web Session Hijacking Defense for Windows Servers in Air-Gapped Networks (Foundational Maturity)
description: "Web Session Hijacking defense playbook for Windows Servers in Air-Gapped Networks at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, windows, server, air-gap, ot, high-security, maturity-foundational]
version: 1.0.0
---
# Web Session Hijacking Defense for Windows Servers in Air-Gapped Networks (Foundational Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to Windows Servers in Air-Gapped Networks at Foundational maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log (7045 service installs, 4720 account creation, 4732 group changes) and IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\Windows\System32\Tasks; run `Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message` then `Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter "Name='$($_.Name)'" | Select-Object Name, PathName, StartName }`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for Windows Servers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
