---
skill_id: cyber_detecting_misconfigured_azure_storage
name: Detecting Misconfigured Azure Storage
description: Find and remediate publicly exposed or over-permissive Azure Storage accounts.
risk: low
permissions: []
requires_confirmation: false
tags: [azure, cloud, misconfiguration]
version: 1.0.0
---
## Purpose

Azure Storage accounts holding blobs, files, and backups are routinely exposed to the internet through permissive network rules, anonymous blob access, or overly broad SAS tokens — a leading cause of cloud data leaks. This playbook is a defensive audit-and-detect guide: discovering your storage footprint, identifying dangerous configurations, and detecting exploitation attempts.

## When to use

- A new subscription or migration needs a storage-security review.
- Threat intel or a researcher reports an exposed company storage account.
- You need continuous detection for storage misconfiguration drift.
- Incident response suspects data was exfiltrated from a storage account.

## Prerequisites

- Reader (or Security Reader) access to Azure subscriptions; Azure Policy/Defender for Cloud visibility helps.
- Inventory of storage accounts across subscriptions, including those created outside central IT.
- Azure Activity logs and Storage diagnostic logs (read/write/delete operations) flowing to Log Analytics/Sentinel.
- Data classification knowledge: which accounts hold sensitive data (backups, PII, source code).

## Procedure

1. Discover the full footprint. Enumerate storage accounts across all subscriptions and tenants — include forgotten dev/test accounts. For each, record: public network access setting, firewall/virtual-network rules, anonymous blob access state, and whether private endpoints are used. Shadow accounts outside central management are the highest risk.
2. Flag dangerous configurations systematically: public network access enabled without firewall rules; anonymous (public) blob/container access; SAS tokens with broad permissions, long expiry, or IP-unrestricted scope; shared-key authorization where Entra ID could be used; and missing soft-delete/versioning on accounts holding critical data.
3. Detect exploitation in the logs. Alert on: anonymous or unexpected-IP read spikes (bulk GETs), List operations from unfamiliar principals, SAS-token usage from unusual geographies, and delete/versioning-disable operations (ransomware precursor). Correlate storage data-plane logs with identity logs — a new external IP reading terabytes is an incident, not a metric.
4. Validate findings before sounding alarms. Confirm whether 'public' access is genuinely anonymous-reachable (test from an external vantage point where authorized) versus merely lacking firewall rules but still key-protected. Prioritize confirmed-anonymous plus sensitive-data combinations.
5. Remediate in risk order: disable anonymous blob access, restrict network rules to required VNets/IPs, revoke and reissue over-broad SAS tokens with tight scope/expiry/IP binding, enforce Entra ID-only authorization, and enable soft delete and versioning. Track each account to a verified-clean state.
6. Prevent drift with policy. Deploy Azure Policy to deny public blob access and require private endpoints/VNet rules on new accounts, alert on policy non-compliance, and run the discovery scan on a schedule — misconfigurations reappear with every new project.

## Expected outputs

- Complete storage-account inventory with configuration findings and risk ratings.
- Detection rules for anomalous storage access (bulk reads, anonymous access, SAS abuse).
- Remediation tracker: account → finding → fix → verification.
- Azure Policy assignments preventing recurrence, with compliance reporting.

## Pitfalls

- 'Public network access enabled' alone doesn't mean anonymously readable — validate before escalating.
- SAS tokens are bearer credentials: revoking the token without finding where it leaked leaves the exposure.
- Legitimate CDN, partner, and data-pipeline access looks like external reads — baseline before alerting.
- Storage accounts in dev/test subscriptions get forgotten; scope discovery to ALL subscriptions.
- Enabling firewall rules without testing breaks applications — stage changes and verify workloads.

## References

- Microsoft Learn: Azure Storage security best practices; CIS Microsoft Azure Foundations Benchmark (storage controls); MITRE ATT&CK T1530 (Data from Cloud Storage) — https://attack.mitre.org/techniques/T1530/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
