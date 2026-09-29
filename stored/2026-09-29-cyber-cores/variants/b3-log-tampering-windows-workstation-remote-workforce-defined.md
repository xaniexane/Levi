---
skill_id: cyber_b3_log_tampering_windows_workstation_remote_workforce_defined
name: Log Tampering Defense for Windows Workstations in Remote Workforce (Defined Maturity)
description: "Log Tampering defense playbook for Windows Workstations in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, windows, endpoint, remote, zero-trust, maturity-defined]
version: 1.0.0
---
# Log Tampering Defense for Windows Workstations in Remote Workforce (Defined Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to Windows Workstations in Remote Workforce at Defined maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: Sysmon + EDR + PowerShell script-block logging forwarded to the SIEM. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security event log (4624/4625 logons, 4688 process creation, 7045 service installs) and Sysmon operational log and PowerShell operational log (4104 script blocks); run `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 | Format-List TimeCreated, @{n='TargetUser';e={$_.Properties[5].Value}}, @{n='SourceIP';e={$_.Properties[19].Value}}` then `autorunsc64.exe -accepteula -a * -c -h -s -t | findstr /v "Microsoft Corporation"`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: Application allowlisting (WDAC/AppLocker) and LSA Protection + Credential Guard enabled. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for Windows Workstations; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
