---
skill_id: cyber_b3_log_tampering_active_directory_dc_azure_cloud_defined
name: Log Tampering Defense for Active Directory Domain Controllers in Azure Cloud (Defined Maturity)
description: "Log Tampering defense playbook for Active Directory Domain Controllers in Azure Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, windows, identity, active-directory, cloud, azure, maturity-defined]
version: 1.0.0
---
# Log Tampering Defense for Active Directory Domain Controllers in Azure Cloud (Defined Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to Active Directory Domain Controllers in Azure Cloud at Defined maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: forwarded Security logs (4768/4769/4771/4662/4720/4732/4724/5136) + AD replication monitoring. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Security log Kerberos events (4768 TGT requests, 4769 service tickets, 4771 pre-auth failures) and Directory-service change events (5136/5137) and replication metadata (repadmin /showobjmeta); run `repadmin /showrepl | Select-String -Pattern 'error|fail' -Context 2` then `Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4769} -MaxEvents 200 | Group-Object {$_.Properties[0].Value} | Sort-Object Count -Descending | Select-Object -First 10 Name, Count`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: Tier-zero isolation: DCs on dedicated hosts, no browsing/email, admin access via PAW/jump host only. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for Active Directory Domain Controllers; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
