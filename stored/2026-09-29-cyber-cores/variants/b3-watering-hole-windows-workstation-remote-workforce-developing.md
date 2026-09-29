---
skill_id: cyber_b3_watering_hole_windows_workstation_remote_workforce_developing
name: Watering Hole Attack Defense for Windows Workstations in Remote Workforce (Developing Maturity)
description: "Watering Hole Attack defense playbook for Windows Workstations in Remote Workforce at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, windows, endpoint, remote, zero-trust, maturity-developing]
version: 1.0.0
---
# Watering Hole Attack Defense for Windows Workstations in Remote Workforce (Developing Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to Windows Workstations in Remote Workforce at Developing maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security event log (4624/4625 logons, 4688 process creation, 7045 service installs) and Sysmon operational log and PowerShell operational log (4104 script blocks); run `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}` then `autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v "Microsoft Corporation"`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for Windows Workstations; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
