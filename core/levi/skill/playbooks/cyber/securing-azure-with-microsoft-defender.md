---
skill_id: cyber_securing_azure_with_microsoft_defender
name: Securing Azure with Microsoft Defender
description: Deploy Microsoft Defender for Cloud: enable plans, remediate Secure Score findings, and centralize alerts.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, azure, defender]
version: 1.0.0
---
## Purpose
Microsoft Defender for Cloud provides CSPM and workload protection across Azure (and hybrid/multicloud). This playbook covers rolling it out as the backbone of Azure security: enabling the right plans, driving Secure Score remediation, routing alerts to the SOC, and using its regulatory compliance views for audit evidence.

## When to use
- New Azure landing zone security baseline.
- Consolidating fragmented Azure security tooling.
- Compliance programs needing continuous Azure posture evidence.
- After incidents revealing gaps in cloud workload protection.

## Prerequisites
- Owner access on target subscriptions and management groups.
- Log Analytics workspace design and Sentinel/SIEM integration plan.
- Asset inventory: which subscriptions host production workloads.
- SOC runbooks for triaging Defender alerts.

## Procedure
1. Enable Defender for Cloud on all in-scope subscriptions; turn on relevant Defender plans (Servers, App Service, SQL, Storage, Containers, Key Vault).
2. Enable auto-provisioning of the monitoring agent where the plan requires it.
3. Review Secure Score: prioritize recommendations by severity and exploitability, assign owners.
4. Remediate top findings first: public storage, missing disk encryption, exposed management ports, unrestricted NSGs.
5. Stream Defender alerts and recommendations to Sentinel/SIEM; tune alert routing and suppression rules.
6. Use workflow automation for common responses: isolate VM, open ticket, notify owner.
7. Enable regulatory compliance views (e.g. CIS, NIST) for continuous audit evidence.
8. Track Secure Score trends and alert true-positive rates monthly; adjust plans as workloads change.
9. Onboard hybrid and Arc-connected servers so Defender for Servers covers on-prem estates.
10. Map Defender recommendations to owners with SLAs; unowned recommendations never get fixed.
11. Test workflow-automation playbooks in a non-production subscription first.

## Expected outputs
- Defender for Cloud enablement record per subscription and plan.
- Secure Score remediation backlog with owners and progress.
- SIEM-integrated alerting with tuned routing and automation.
- Arc onboarding status for hybrid servers.
- Recommendation ownership matrix with SLAs.
- Validated automation playbooks for common alerts.

## Pitfalls
- Enabling every plan everywhere wastes budget; scope plans to actual workload types.
- Auto-provisioning agents on all VMs can conflict with existing EDR; coordinate rollout.
- Secure Score is a hygiene proxy, not a risk score; pair it with threat-informed priorities.
- Alert fatigue is real; tune and automate before expanding plan coverage.
- Defender plan costs scale per resource; right-size plans to workload types.
- Recommendations without owners accumulate; assign every one.
- Auto-remediation playbooks can cause outages if untested; validate first.
- Recommendations marked 'not applicable' need justification; otherwise teams hide real gaps there.

## References
- Microsoft Learn: Microsoft Defender for Cloud documentation.
- Microsoft Learn: Secure Score in Defender for Cloud.
- CIS Microsoft Azure Foundations Benchmark.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
