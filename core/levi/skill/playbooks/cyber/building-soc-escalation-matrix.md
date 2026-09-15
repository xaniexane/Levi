---
skill_id: cyber_building_soc_escalation_matrix
name: Building a SOC Escalation Matrix
description: Practitioner guide to designing a clear escalation matrix that routes security alerts to the right people at the right speed.
risk: info
permissions: []
requires_confirmation: false
tags: [soc, operations, incident-response]
version: 1.0.0
---
## Purpose
Alerts that sit in a queue or bounce between teams are how breaches become disasters. An escalation matrix defines, for each alert category and severity, who handles it, who gets notified, and how fast each step must happen. This playbook builds that matrix and the operating discipline to keep it current.

## When to use
- Standing up SOC operations or formalizing an informal on-call rotation.
- Fixing slow or inconsistent response times to critical alerts.
- Clarifying responsibilities between SOC tiers, IR, IT, and business units.
- Auditing whether the right stakeholders are engaged for each incident type.

## Prerequisites
- Alert taxonomy: categories and severity definitions used by the SOC.
- Organizational chart with current on-call rotations and contact methods.
- Defined SLAs or response-time objectives per severity.
- Executive agreement on who can be woken up and for what.

## Procedure
1. Catalog alert categories. List the detection types the SOC handles (malware, phishing, intrusion, DLP, availability) and their severity tiers.
2. Define tier responsibilities. Specify what Tier 1 triages, what Tier 2 investigates, and what goes to incident response or engineering.
3. Assign owners and backups. Name the team or role for each category and severity, plus a backup path when the primary is unreachable.
4. Set time thresholds. Define acknowledge, escalate, and resolve targets per severity; make them measurable in the ticketing system.
5. Map notification paths. Specify the channel for each escalation step (ticket, chat, page, phone) and when to switch from async to synchronous.
6. Include business escalation. Define when executives, legal, PR, and customers enter the picture, and who makes that call.
7. Publish and train. Put the matrix where analysts can reach it in seconds; walk through it in onboarding and exercises.
8. Review regularly. Update after every org change, tool change, or missed SLA; audit a sample of escalations quarterly.

## Expected outputs
- Published escalation matrix covering categories, severities, owners, and SLAs.
- Notification and on-call procedures integrated with ticketing.
- Quarterly review and audit process.

## Pitfalls
- Matrices built around individuals instead of roles break on the first vacation.
- Unrealistic SLAs that nobody meets train everyone to ignore the matrix.
- Missing business escalation leaves executives learning about incidents from the news.
- A matrix nobody can find in a crisis is the same as no matrix.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- ISO/IEC 27035, Information security incident management
- SANS SOC operational guidance concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
