---
skill_id: cyber_hunting_for_living_off_the_cloud_techniques
name: Hunting for Living-off-the-Cloud Techniques
description: Detect adversaries abusing legitimate cloud services (storage, SaaS APIs, cloud shell) for C2, exfiltration, and persistence.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, cloud, c2]
version: 1.0.0
---
## Purpose

"Living off the cloud" describes attackers using legitimate cloud
services — cloud storage, SaaS APIs, serverless functions, cloud shells —
as C2, exfiltration, and persistence infrastructure that blends into
normal traffic. This playbook covers hunting for cloud-service abuse
across cloud audit logs, CASB/proxy telemetry, and endpoint data.

## When to use

- Investigating intrusions where traditional C2 infrastructure is
  absent (the C2 may be a cloud API).
- Hunting for exfiltration to personal cloud storage or attacker-
  controlled tenants.
- Reviewing cloud audit logs for persistence (rogue OAuth apps, API
  keys, automation rules).
- Validating cloud-detection coverage for your SaaS and IaaS estate.

## Prerequisites

- Cloud audit logs: AWS CloudTrail, Azure Activity Log, GCP Audit Logs,
  and SaaS audit logs (M365 unified audit log, Google Workspace audit).
- CASB or proxy logs showing cloud-service usage with user attribution.
- An inventory of sanctioned cloud services, tenants, and OAuth
  applications.
- Baselines of normal cloud API usage per role and service account.

## Procedure

1. **Inventory legitimate cloud usage.** Document sanctioned tenants,
   storage buckets, SaaS apps, and OAuth grants. Living-off-the-cloud
   hunting is anomaly detection against this inventory — unknown
   tenants and apps are the primary signal.
2. **Hunt rogue OAuth and API integrations.** Review OAuth app consents
   and API keys/tokens: apps with mail/file read-write scopes granted
   outside IT processes, newly created service principals with broad
   permissions, and long-lived tokens created by compromised users.
3. **Hunt cloud storage abuse.** Look for large uploads to personal or
   unknown-tenancy storage, sharing links created on sensitive files,
   and storage access from unusual locations or non-corporate devices.
   Correlate with endpoint staging activity.
4. **Hunt cloud-shell and compute abuse.** Check for Cloud Shell /
   CloudShell usage, unexpected VM or container launches, serverless
   function deployments, and automation (Logic Apps, Cloud Functions)
   created outside change control — all are attacker compute hiding in
   your bill.
5. **Hunt SaaS-as-C2 patterns.** Look for C2-like API polling: regular,
   automated API calls to collaboration, paste, or messaging services
   from server or automation contexts; dead-drop style file reads/writes
   used for tasking.
6. **Review identity and access anomalies.** Correlate cloud findings
   with identity telemetry: impossible-travel logons preceding OAuth
   grants, MFA fatigue approvals, and privilege escalations in the
   cloud control plane.
7. **Scope across the cloud estate.** Attackers with cloud access move
   laterally between services — review all subscriptions, tenants, and
   projects the compromised identity could reach, not just the first
   finding.
8. **Respond and harden.** Revoke rogue OAuth grants and tokens, remove
   attacker-created resources, rotate exposed keys, enforce OAuth app
   allow-listing and admin-consent workflows, and deploy detections for
   the observed abuse patterns.

## Expected outputs

- Findings: rogue apps/tokens, abused storage, attacker compute, with
   timelines.
- Revocation and cleanup records with verification.
- Cloud-inventory vs. sanctioned-baseline gap analysis.
- Detections for cloud-abuse patterns and OAuth governance changes.

## Pitfalls

- Shadow IT means the "sanctioned" inventory is always incomplete —
   treat unknown-but-benign as a governance finding, not just noise.
- Cloud audit logs have variable retention and latency — verify
   coverage before promising hunt completeness.
- Revoking OAuth grants can break business integrations — verify
   ownership before revoking, and have a restore path.
- Attackers use your own tenants — tenant-scoped allow-listing alone
   does not stop abuse; behavior is the signal.
- Multi-cloud estates need per-platform hunts — one cloud's audit log
   does not cover the others.

## References

- MITRE ATT&CK: T1139, T1526-adjacent cloud technique mappings;
  T1078 (Valid Accounts — cloud); T1550 (Use Alternate Auth Material)
- Cloud provider audit-log documentation (CloudTrail, Azure Activity
  Log, GCP Audit Logs, M365 unified audit log)
- CISA: cloud security best-practice guidance
- NIST SP 800-210: General Access Control Guidance for Cloud Systems
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
