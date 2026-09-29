---
skill_id: cyber_b3_dns_fast_flux_windows_server_remote_workforce_defined
name: DNS Fast-Flux Defense for Windows Servers in Remote Workforce (Defined Maturity)
description: "DNS Fast-Flux defense playbook for Windows Servers in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, dns, c2, windows, server, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# DNS Fast-Flux Defense for Windows Servers in Remote Workforce (Defined Maturity)

## Purpose

Fast-flux networks rotate DNS answers across many compromised hosts every few minutes, making malicious infrastructure hard to takedown. Defenders detect the flux pattern itself: low TTLs, high answer churn, and geographically scattered A records. Applies to Windows Servers in Remote Workforce at Defined maturity.

## When to use

- DNS answers with TTLs under 300 seconds rotating across dozens of IPs in unrelated ASNs and countries for a single domain.
- Short-lived domains (registered days ago) resolving to residential or compromised-server IPs with no legitimate business relationship.
- Endpoint connections to flux domains correlating with malware detonations or phishing kit infrastructure.
- Lens: Best telemetry: Security log with advanced audit policy + Sysmon + service-install monitoring. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log (7045 service installs, 4720 account creation, 4732 group changes) and IIS/HTTP.sys logs for web-facing roles; scheduled-task store in C:\Windows\System32\Tasks; run `Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} | Select-Object -First 20 TimeCreated, Message` then `Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object { Get-CimInstance Win32_Service -Filter "Name='$($_.Name)'" | Select-Object Name, PathName, StartName }`.
3. **Analyze.** Profile the flux: record TTL, unique IPs per hour, ASN/country spread, and name-server patterns to fingerprint the specific flux service or kit. Then: Pivot from the domain to find sibling infrastructure: shared name servers, registration patterns, and certificate overlaps.
4. **Contain and harden.** DNS response policy zones (RPZ) blocking confirmed flux domains, plus alerting on sub-300s TTL answers at the resolver. Asset layer: Server Core installs where possible; disable unnecessary roles and SMBv1; enforce SMB signing. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking individual flux IPs — they churn in minutes; block the domain pattern and the detection logic instead.
- Confusing legitimate CDN behavior (low TTL, many IPs) with flux; require the ASN-scatter plus short-domain-age combination.

## References

- MITRE ATT&CK: T1568.002 (Command and Control: Domain Generation Algorithms)
- Vendor logging and hardening baselines for Windows Servers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
