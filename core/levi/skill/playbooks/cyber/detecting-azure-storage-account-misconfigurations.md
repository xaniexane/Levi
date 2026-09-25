---
skill_id: cyber_detecting_azure_storage_account_misconfigurations
name: Detecting Azure Storage Account Misconfigurations
description: Audit Azure Storage for public exposure, weak auth, and insecure transfer settings with continuous monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [azure, cloud, hardening]
version: 1.0.0
---
## Purpose

Find and fix the Azure Storage misconfigurations that cause data breaches: public blob access, overly permissive SAS tokens, missing encryption, and insecure transfer settings — then keep them fixed with continuous monitoring.

## When to use

- Auditing Azure Storage across subscriptions for public-exposure risk.
- Responding to a suspected data leak from a storage account.
- Building storage-security baselines for compliance (CIS Azure benchmark).
- Validating that IaC templates don't deploy insecure storage defaults.

## Prerequisites

- Reader access across subscriptions (or Azure Policy / Defender for Cloud reporting).
- An inventory of storage accounts with data classification (public content vs. sensitive).
- Azure Policy or a scanning tool (Prowler, ScoutSuite, or custom scripts) for continuous assessment.
- Authority to remediate: change network rules, disable public access, rotate keys.

## Procedure

1. **Inventory every storage account and classify it.** List all storage accounts across subscriptions with: public access settings, network rules, data classification, and owner. You can't protect what you haven't inventoried — subscriptions created outside central IT are where the exposures hide.
2. **Eliminate public blob access.** Check `allowBlobPublicAccess` on every account — disable it wherever the data isn't intentionally public. Then check container-level public access settings; account-level disable doesn't retroactively fix containers made public. Alert on any re-enablement as a high-severity finding.
3. **Lock down network access.** Set `defaultAction: Deny` on the storage firewall and allowlist only required VNets and IPs. Enable private endpoints for sensitive accounts so traffic never crosses the public internet. Alert on firewall rule changes and new public-network access.
4. **Harden authentication.** Require Microsoft Entra authorization for the data plane where possible; disable shared-key authorization on sensitive accounts (it bypasses Conditional Access and RBAC). Audit SAS tokens: short expiries, IP restrictions, HTTPS-only, and minimal permissions — a full-permission, long-lived SAS in a repo is a breach waiting for a scanner.
5. **Enforce encryption and secure transfer.** Require secure transfer (HTTPS-only), enable infrastructure encryption for highly sensitive data, and confirm customer-managed keys are used where policy requires. Check that storage account keys are rotated regularly — or better, eliminate key usage in favor of managed identities.
6. **Monitor the data plane.** Enable diagnostic logging (read/write/delete) on sensitive accounts and alert on: anonymous access attempts, mass download patterns, access from unexpected geographies, and permission changes on containers. Defender for Cloud's storage protections provide anomaly baselines — enable and tune them.
7. **Gate deployments with policy.** Deploy Azure Policy initiatives (CIS benchmark-based) that deny non-compliant storage configurations at creation time: no public access, secure transfer required, minimum TLS version. Prevention at deploy time beats detection after exposure.

## Expected outputs

- A classified storage inventory with public access eliminated and network rules default-deny.
- Hardened authentication (Entra preferred, SAS tokens scoped and short-lived) with rotation.
- Azure Policy deny-gates on insecure configurations plus data-plane anomaly alerting.

## Pitfalls

- Disabling account-level public access but missing container-level settings — the exposure persists.
- Shared-key authorization left on — it bypasses every Conditional Access policy you wrote.
- Long-lived, broad SAS tokens — treat them like passwords: scoped, short-lived, rotated.
- No diagnostic logging on the data plane — you discover the exfiltration from the news, not your SIEM.
- IaC templates with insecure defaults — every new deployment recreates the misconfiguration.

## References

- Microsoft Learn — Azure Storage security guide, shared key vs. Entra authorization, SAS best practices
- CIS Microsoft Azure Foundations Benchmark — storage controls
- MITRE ATT&CK T1530 (Data from Cloud Storage Object)
- NIST SP 800-53 SC-12 / SC-28 (cryptographic protection, protection of information at rest)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
