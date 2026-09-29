---
skill_id: cyber_b3_cloud_console_takeover_azure_subscription_hybrid_cloud_developing
name: Cloud Console Takeover Defense for Azure Subscriptions in Hybrid Cloud (Developing Maturity)
description: "Cloud Console Takeover defense playbook for Azure Subscriptions in Hybrid Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, identity, azure, hybrid, on-prem, maturity-developing]
version: 1.0.0
---
# Cloud Console Takeover Defense for Azure Subscriptions in Hybrid Cloud (Developing Maturity)

## Purpose

Stolen cloud credentials used in the web console give attackers point-and-click infrastructure control. Console logons from unusual locations followed by IAM changes are the classic takeover sequence. Applies to Azure Subscriptions in Hybrid Cloud at Developing maturity.

## When to use

- CloudTrail/Entra sign-in logs showing console logons from new countries or anonymizing services for privileged users.
- IAM policy changes, new access keys, or new users created within minutes of the anomalous logon.
- Disabling of CloudTrail/logging or deletion of log data — the attacker covering tracks.
- Lens: Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Azure Activity Log (write/delete on IAM, policy, network) and Entra audit/sign-in logs and Defender for Cloud recommendations and alerts; resource-change history; run `az monitor activity-log list --max-events 25 --query '[].{time:eventTimestamp, op:operationName.value, caller:caller}' -o table` then `az security alert list --query '[].{name:alertDisplayName, severity:severity, time:timeGeneratedUtc}' -o table`.
3. **Analyze.** Reconstruct the full API call sequence after takeover: what was created, modified, exfiltrated, or destroyed. Then: Check for persistence: new IAM users, roles with trust policies pointing outward, or modified instance user-data.
4. **Contain and harden.** Phishing-resistant MFA on all console users, especially root/ break-glass; SCPs preventing logging disablement. Asset layer: Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the compromised user's keys but missing the backdoor IAM role the attacker created.
- Trusting the account's own logs after the attacker had admin — verify against the immutable archive.

## References

- MITRE ATT&CK: T1078 (Persistence: Valid Accounts) — cloud console
- Vendor logging and hardening baselines for Azure Subscriptions; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
