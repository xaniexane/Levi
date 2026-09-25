---
skill_id: cyber_building_cloud_siem_with_sentinel
name: Building a Cloud SIEM with Microsoft Sentinel
description: Practitioner guide to deploying and tuning Microsoft Sentinel as a cloud-native SIEM, from workspace design to detection rules and automation.
risk: info
permissions: []
requires_confirmation: false
tags: [detection, siem, cloud]
version: 1.0.0
---
## Purpose
This playbook walks a security team through standing up Microsoft Sentinel: workspace architecture, data-connector strategy, detection engineering, automation with playbooks, and operational handoff. It is a build guide for defenders, aimed at producing a maintainable, cost-conscious SIEM rather than a connector-sprawl project.

## When to use
- Standing up a first cloud-native SIEM or migrating from an on-premises SIEM.
- Consolidating security telemetry across Azure, Microsoft 365, and third-party sources.
- Preparing for SOC operations that need detection-as-code and automated response.
- Reviewing an existing Sentinel deployment for cost or coverage problems.

## Prerequisites
- Azure subscription with permissions to create Log Analytics workspaces and Sentinel resources.
- Inventory of log sources and retention requirements (regulatory and operational).
- Identity for automation: a service principal or managed identity for playbooks.
- Defined detection priorities and alert routing (who gets paged, for what).

## Procedure
1. Design the workspace strategy. Decide between a single workspace and per-region or per-business-unit workspaces; document retention tiers and data-residency constraints.
2. Deploy Log Analytics and enable Sentinel. Create the workspace, turn on Sentinel, and set daily caps and commitment tiers to control cost from day one.
3. Connect core sources first. Enable Microsoft-native connectors (Entra ID, Microsoft 365 Defender, Azure Activity) before third-party ones, and verify data is flowing.
4. Add third-party connectors deliberately. For each, confirm you need the data for a specific detection; avoid enabling everything available.
5. Normalize with ASIM. Apply the Advanced Security Information Model parsers where possible so detections are portable across sources.
6. Build detections as code. Write KQL analytics rules covering your top threats, version them in source control, and deploy through pipelines rather than the portal.
7. Automate triage with playbooks. Use Logic Apps automation rules for enrichment, ticket creation, and low-risk containment; keep human approval on high-impact actions.
8. Tune and hand off. Run the SIEM for two to four weeks, measure false-positive rates and cost per ingested gigabyte, tune rules, then hand documented runbooks to the SOC.

## Expected outputs
- Sentinel deployment with documented workspace design and cost controls.
- Version-controlled KQL detection set mapped to MITRE ATT&CK.
- Automation playbooks for enrichment, notification, and containment.
- SOC handoff package: runbooks, escalation paths, and tuning backlog.

## Pitfalls
- Ingesting everything without a cost model leads to runaway bills; cap and tier early.
- Portal-built rules that are not versioned become unmaintainable within months.
- Enabling connectors without parsers or detections produces data nobody looks at.
- Over-automating containment without approval gates risks business disruption.

## References
- Microsoft Learn: Microsoft Sentinel documentation
- Microsoft Learn: Kusto Query Language (KQL) reference
- MITRE ATT&CK for detection mapping
- NIST SP 800-92, Guide to Computer Security Log Management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
