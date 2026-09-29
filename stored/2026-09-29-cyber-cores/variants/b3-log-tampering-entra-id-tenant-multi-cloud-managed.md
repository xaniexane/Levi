---
skill_id: cyber_b3_log_tampering_entra_id_tenant_multi_cloud_managed
name: Log Tampering Defense for Microsoft Entra ID Tenants in Multi-Cloud (Managed Maturity)
description: "Log Tampering defense playbook for Microsoft Entra ID Tenants in Multi-Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, identity, cloud, microsoft, multi-cloud, maturity-managed]
version: 1.0.0
---
# Log Tampering Defense for Microsoft Entra ID Tenants in Multi-Cloud (Managed Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to Microsoft Entra ID Tenants in Multi-Cloud at Managed maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
