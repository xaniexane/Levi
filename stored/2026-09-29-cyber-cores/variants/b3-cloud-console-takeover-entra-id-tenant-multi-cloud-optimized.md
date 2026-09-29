---
skill_id: cyber_b3_cloud_console_takeover_entra_id_tenant_multi_cloud_optimized
name: Cloud Console Takeover Defense for Microsoft Entra ID Tenants in Multi-Cloud (Optimized Maturity)
description: "Cloud Console Takeover defense playbook for Microsoft Entra ID Tenants in Multi-Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, identity, microsoft, multi-cloud, maturity-optimized]
version: 1.0.0
---
# Cloud Console Takeover Defense for Microsoft Entra ID Tenants in Multi-Cloud (Optimized Maturity)

## Purpose

Stolen cloud credentials used in the web console give attackers point-and-click infrastructure control. Console logons from unusual locations followed by IAM changes are the classic takeover sequence. Applies to Microsoft Entra ID Tenants in Multi-Cloud at Optimized maturity.

## When to use

- CloudTrail/Entra sign-in logs showing console logons from new countries or anonymizing services for privileged users.
- IAM policy changes, new access keys, or new users created within minutes of the anomalous logon.
- Disabling of CloudTrail/logging or deletion of log data — the attacker covering tracks.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Reconstruct the full API call sequence after takeover: what was created, modified, exfiltrated, or destroyed. Then: Check for persistence: new IAM users, roles with trust policies pointing outward, or modified instance user-data.
4. **Contain and harden.** Phishing-resistant MFA on all console users, especially root/ break-glass; SCPs preventing logging disablement. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the compromised user's keys but missing the backdoor IAM role the attacker created.
- Trusting the account's own logs after the attacker had admin — verify against the immutable archive.

## References

- MITRE ATT&CK: T1078 (Persistence: Valid Accounts) — cloud console
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
