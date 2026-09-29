---
skill_id: cyber_b3_cryptominer_intrusion_gcp_project_aws_cloud_foundational
name: Cryptominer Intrusion Defense for GCP Projects in AWS Cloud (Foundational Maturity)
description: "Cryptominer Intrusion defense playbook for GCP Projects in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [malware, cloud, gcp, aws, maturity-foundational]
version: 1.0.0
---
# Cryptominer Intrusion Defense for GCP Projects in AWS Cloud (Foundational Maturity)

## Purpose

Unauthorized miners burn CPU/GPU and cloud spend, and — more importantly — prove an attacker has code execution on your assets. Treat every miner as a foothold to investigate, not just a performance problem. Applies to GCP Projects in AWS Cloud at Foundational maturity.

## When to use

- Sustained high CPU/GPU on hosts or cloud instances with no business workload, especially at night/weekends, plus connections to known mining pools on Stratum ports.
- Cloud billing spikes for compute in regions you do not use, or new instances launched by unfamiliar principals.
- EDR detections for xmrig or similar binaries, scheduled tasks re-fetching miner payloads, or WMI persistence entries.
- Lens: Best telemetry: Cloud Audit Logs (Admin Activity + Data Access) + Security Command Center + VPC flow logs. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Cloud Audit Logs: setIamPolicy, storage.setIamPermissions, compute inserts, and console logons and Security Command Center findings; Forseti/Config Validator drift reports where deployed; run `gcloud logging read 'protoPayload.methodName:"SetIamPolicy"' --limit 20 --format='table(timestamp, protoPayload.authenticationInfo.principalEmail, resourceName)'` then `gcloud scc findings list organizations/$ORG_ID --filter='state="ACTIVE"' --limit 15`.
3. **Analyze.** Trace the miner's persistence and delivery: the initial access vector (exposed service, weak SSH, vulnerable app) matters more than the miner itself. Then: Check for dual-use: many miner campaigns also exfiltrate credentials or deploy additional payloads — sweep for those.
4. **Contain and harden.** Close the entry vector (patch the exploited service, enforce key-based SSH, remove internet exposure), then block mining pool domains at DNS. Asset layer: Organization policies: no public buckets, no default SA use, OS Login on; deny unapproved APIs. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the miner without removing persistence — it returns on reboot or on schedule.
- Writing it off as 'just a miner' without investigating the initial access that delivered it.

## References

- MITRE ATT&CK: T1496 (Impact: Resource Hijacking)
- Vendor logging and hardening baselines for GCP Projects; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
