---
skill_id: cyber_b3_insider_data_theft_api_gateway_multi_cloud_foundational
name: Insider Data Theft Defense for API Gateways in Multi-Cloud (Foundational Maturity)
description: "Insider Data Theft defense playbook for API Gateways in Multi-Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, web, api, cloud, multi-cloud, maturity-foundational]
version: 1.0.0
---
# Insider Data Theft Defense for API Gateways in Multi-Cloud (Foundational Maturity)

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. Applies to API Gateways in Multi-Cloud at Foundational maturity.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context
- Vendor logging and hardening baselines for API Gateways; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
