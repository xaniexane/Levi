---
skill_id: cyber_implementing_ticketing_system_for_incidents
name: Implementing a Ticketing System for Incidents
description: Design incident ticketing workflows that keep response fast, tracked, and auditable.
risk: low
permissions: []
requires_confirmation: false
tags: [incident-response, ticketing, soc-operations]
version: 1.0.0
---
## Purpose
This playbook defines how to configure and operate an incident ticketing system (Jira, ServiceNow, TheHive, or similar) so every security incident gets consistent intake, prioritization, tasking, and closure evidence.

## When to use
- Incidents are handled in chat threads and email with no durable record.
- Auditors or regulators ask for evidence of incident handling and timelines.
- Multiple teams (SOC, IT, legal, comms) need coordinated tasking during response.

## Prerequisites
- Chosen ticketing platform with admin access and API/integration options.
- Defined incident severity levels and SLAs agreed with stakeholders.
- Integration points: SIEM/SOAR for auto-creation, CMDB for asset context, comms channels for notifications.

## Procedure
1. **Design the incident issue type.** Create a dedicated type with fields for severity, category, ATT&CK techniques, affected assets, timeline, and root cause — separate from generic IT tickets.
2. **Build the workflow.** States should mirror your IR process: triage, scoping, containment, eradication, recovery, lessons learned, closed. Restrict transitions so closure requires completed post-incident fields.
3. **Automate creation and enrichment.** Have the SIEM/SOAR open tickets with alert context pre-filled; auto-assign based on severity, asset owner, or on-call rotation.
4. **Standardize tasking.** Use checklists or sub-tasks per incident category so containment steps are not forgotten under pressure.
5. **Control access and sensitivity.** Restrict incident tickets to responders; mask or compartmentalize tickets involving executives, HR matters, or regulated data.
6. **Enforce the timeline.** Require timestamped entries for key milestones; generate the incident timeline from the ticket for reporting.
7. **Close with lessons learned.** Block closure until root cause, corrective actions, and detection improvements are recorded and assigned owners.

8. **Integrate with the war room.** During major incidents, auto-create a shared chat channel linked from the ticket so coordination happens in one place and is captured.
9. **Measure ticket quality.** Sample closed incidents quarterly for timeline completeness, root-cause quality, and follow-up execution; bad tickets indicate process failure, not analyst failure.

## Expected outputs
- Configured incident workflow with required fields and transition guards.
- Integration from detection tooling to ticket creation with enrichment.
- Metrics: time to acknowledge, time to contain, SLA compliance, repeat-incident rate.
- Example: a SIEM critical alert auto-creates a ticket with asset context and ATT&CK tags, pages the on-call, and blocks closure until root cause and corrective actions are recorded.

## Pitfalls
- Reusing the generic IT helpdesk workflow: security incidents need different fields and urgency.
- Tickets that can be closed with no root cause or follow-up actions.
- Over-sharing sensitive incident details with broad IT audiences.

- Auto-created tickets with no deduplication flooding the queue during a widespread event; implement alert grouping before auto-creation.
- Ticket comments becoming the only record of key decisions; require decision entries in dedicated fields, not buried in comment threads.

## References
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- TheHive Project documentation (thehive-project.org) for IR-centric case management.
- SANS SEC504 (sans.org) — incident handling process and documentation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
