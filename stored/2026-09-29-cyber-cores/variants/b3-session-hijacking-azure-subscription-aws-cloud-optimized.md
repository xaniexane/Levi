---
skill_id: cyber_b3_session_hijacking_azure_subscription_aws_cloud_optimized
name: Web Session Hijacking Defense for Azure Subscriptions in AWS Cloud (Optimized Maturity)
description: "Web Session Hijacking defense playbook for Azure Subscriptions in AWS Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, cloud, azure, aws, maturity-optimized]
version: 1.0.0
---
# Web Session Hijacking Defense for Azure Subscriptions in AWS Cloud (Optimized Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to Azure Subscriptions in AWS Cloud at Optimized maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Azure Activity Log (write/delete on IAM, policy, network) and Entra audit/sign-in logs and Defender for Cloud recommendations and alerts; resource-change history; run `az monitor activity-log list --max-events 25 --query '[].{time:eventTimestamp, op:operationName.value, caller:caller}' -o table` then `az security alert list --query '[].{name:alertDisplayName, severity:severity, time:timeGeneratedUtc}' -o table`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for Azure Subscriptions; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
