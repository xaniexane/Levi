---
skill_id: cyber_b3_watering_hole_aws_account_air_gapped_network_optimized
name: Watering Hole Attack Defense for AWS Accounts in Air-Gapped Networks (Optimized Maturity)
description: "Watering Hole Attack defense playbook for AWS Accounts in Air-Gapped Networks at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, cloud, aws, air-gap, ot, high-security, maturity-optimized]
version: 1.0.0
---
# Watering Hole Attack Defense for AWS Accounts in Air-Gapped Networks (Optimized Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to AWS Accounts in Air-Gapped Networks at Optimized maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: CloudTrail (org trail, all regions) + GuardDuty + VPC flow logs + Config. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in CloudTrail event history (console logons, IAM changes, AssumeRole, security-group changes) and GuardDuty findings, IAM Access Analyzer results, and S3 server-access logs for data stores; run `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-items 20` then `aws iam generate-credential-report && aws iam get-credential-report --query Content --output text | base64 -d | head -5`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: MFA on root + all IAM users, SCPs denying logging disablement and unapproved regions, no long-lived keys. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for AWS Accounts; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
