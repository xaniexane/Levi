---
skill_id: cyber_building_incident_response_dashboard
name: Building an Incident Response Dashboard
description: Practitioner guide to designing an incident-response dashboard that gives commanders real-time visibility into case status, tasks, and metrics.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, metrics, operations]
version: 1.0.0
---
## Purpose
During a major incident, scattered chat threads and spreadsheets cost time and lose track of decisions. This playbook builds a single dashboard that shows open incidents, assigned tasks, evidence status, communications log, and key metrics, so the incident commander maintains shared situational awareness from detection through closure.

## When to use
- Standing up or maturing an incident-response capability.
- Preparing for tabletop exercises and real major incidents.
- Replacing ad-hoc spreadsheets with a structured case view.
- Reporting incident status to executives who need a single pane of glass.

## Prerequisites
- Case-management or ticketing system that exposes incident data (API or export).
- Agreed incident-severity levels and role definitions (commander, lead, comms).
- Communication channels (chat, bridge) whose key events can be logged.
- Metrics definitions agreed with stakeholders (MTTD, MTTR, tasks overdue).

## Procedure
1. Define the audience and decisions. List who views the dashboard (commander, executives, legal) and which decisions each view must support.
2. Select the data sources. Connect the case tracker, task list, evidence inventory, and communications log; define refresh cadence for each.
3. Design the commander view. Show active incidents by severity, open tasks with owners and due times, containment milestones, and outstanding decisions.
4. Design the executive view. Show business impact, customer exposure, estimated recovery time, and communication status without technical detail.
5. Build task tracking. Every action item gets an owner, a due time, and a status; overdue items surface prominently and automatically.
6. Add evidence and chain-of-custody status. Track what was collected, where it is stored, and who has handled it.
7. Integrate the communications log. Record notifications sent, to whom, and when, so nothing is double-sent or missed.
8. Exercise and refine. Use the dashboard in tabletop exercises; fix gaps in data, layout, and permissions before a real incident.

## Expected outputs
- Operational IR dashboard with commander and executive views.
- Task, evidence, and communications tracking integrated into case workflow.
- Exercise-validated layout and access controls.

## Pitfalls
- Dashboards fed by manually updated spreadsheets go stale within hours; automate feeds.
- Showing executives raw technical detail creates confusion instead of confidence.
- Too many metrics dilute attention; keep the commander view to what drives decisions.
- Access controls forgotten in a crisis leak sensitive details to the wrong audience.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- CISA incident response resources and exercise guidance
- SANS incident handler's handbook concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
