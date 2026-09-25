---
skill_id: cyber_implementing_azure_defender_for_cloud
name: Microsoft Defender for Cloud
description: Deploy Defender for Cloud across Azure (and multicloud) for CSPM, workload protection, and alert triage.
risk: low
permissions: []
requires_confirmation: false
tags: [azure, cloud-security]
version: 1.0.0
---
## Purpose
Defender for Cloud is Azure's combined posture-management and threat-protection plane: secure score,
regulatory-compliance dashboards, and Defender plans that add threat detection per workload
(servers, containers, databases, storage). This playbook deploys it tenant-wide with tuned plans,
alert routing, and remediation workflows — the Azure counterpart to the AWS Security Hub playbook.

## When to use
- Centralizing Azure (and AWS/GCP, via multicloud connectors) security monitoring.
- After incidents where misconfigurations or threats went unnoticed in Azure.
- Meeting continuous-compliance needs with the built-in regulatory standards.
- Rolling out server/container/database threat protection consistently across subscriptions.
- When leadership wants a single secure-score trend for cloud posture.

## Prerequisites
- Management-group hierarchy designed so Defender plans and policies inherit correctly.
- Defined scope: which subscriptions get which Defender plans (servers, App Service, SQL, storage,
  containers, Key Vault, etc.) — plan costs scale with coverage.
- A SIEM/SOAR destination (Sentinel or third-party) for alert streaming.
- Owner mapping per subscription/resource group for remediation routing.
- Azure Policy baseline understanding: Defender's recommendations are enforced via policy.

## Procedure
1. **Enable at the management-group root.** Turn on Defender for Cloud and enable Defender plans at
   the highest appropriate management group so new subscriptions inherit protection automatically.
   Document which plans are enabled where and the cost implication.
2. **Connect multicloud if applicable.** Add AWS and GCP connectors to bring those estates into the
   same posture view. Verify data flows and align severity handling with the AWS-native tooling
   (avoid double-triaging the same finding in two consoles).
3. **Tune the secure-score recommendations.** Review the initial recommendations; disable or exempt
   those not applicable (with documented justification and expiry), and assign the rest to owners.
   Prioritize: internet-exposed misconfigurations, missing encryption, and absent logging — the same
   exploitability logic as ASM.
4. **Enable Defender plans per workload.** For servers: deploy the Log Analytics/AMA agent or
   Defender-for-servers agentless scanning per plan guidance. For containers, databases, storage,
   Key Vault, and App Service: enable plans matching your actual usage — unused plans are cost
   without coverage.
5. **Stream alerts to the SOC.** Configure continuous export of security alerts and recommendations
   to the SIEM (Sentinel workspace or Event Hub). Define severity handling: High-severity alerts
   (e.g., suspicious process, SQL injection attempt) page; Medium/Low ticket or aggregate.
6. **Tune alert noise.** Common tuning: expected vulnerability-scan sources, approved pen-test
   windows, and known-benign administrative patterns. Use alert suppression rules with expiry and
   justification — never permanent silent rules.
7. **Drive recommendation remediation.** Recommendations are the hardening backlog: assign to
   subscription owners with SLAs, track secure-score trend per subscription, and escalate stagnant
   recommendations. Exemptions require justification and expiry like any exception.
8. **Use regulatory compliance dashboards as evidence.** Map the built-in standards (PCI DSS, NIST,
   ISO) to your audit obligations; export control status for auditors. Treat dashboard gaps as
   findings with owners, not as informational.
9. **Exercise incident workflows.** Quarterly: simulate a High alert (e.g., via a safe test that
   triggers a detection) and walk the SOC through triage, containment (isolate VM, revoke keys), and
   closure. Verify alert latency from Azure to the SIEM meets your SLA.
10. **Report posture trends.** Monthly: secure score trend, recommendation remediation rate, alert
    volume by severity and disposition, plan coverage (percent of eligible resources protected), and
    cost per plan. Present deltas and coverage gaps to leadership.

## Expected outputs
- Defender for Cloud enabled at management-group root with documented plan coverage and multicloud
  connectors.
- Tuned recommendations with owners, SLAs, and a managed exemption process.
- Alerts streaming to the SIEM with severity-based routing and tuned suppressions.
- Quarterly incident-workflow exercises and monthly posture trend reports.
- Regulatory-compliance dashboard mapped to audit evidence needs.

## Pitfalls
- Enabling plans without cost review: per-resource Defender plans (especially servers) add up fast —
  scope to real usage and monitor spend.
- Recommendations without owners: a 60% secure score with no remediation loop is a dashboard, not a
  program.
- Treating secure score as a security metric: it's a hygiene proxy. Pair it with alert MTTR and
  incident outcomes.
- Alert fatigue from untuned Medium/Low alerts: route by severity and tune aggressively in the first
  month or the SOC will ignore the feed.
- Forgetting new subscriptions: enablement at the management group prevents this — verify
  inheritance after every new subscription creation.

## References
- Microsoft Learn: Microsoft Defender for Cloud documentation (plans, secure score, alert streaming)
- CIS Microsoft Azure Foundations Benchmark
- NIST SP 800-53 CA-7, SI-4 (continuous monitoring)
- MITRE ATT&CK cloud techniques (T1078, T1552, T1530) mapped in Defender alert types
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
