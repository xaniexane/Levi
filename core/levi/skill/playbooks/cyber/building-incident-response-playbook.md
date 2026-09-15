---
skill_id: cyber_building_incident_response_playbook
name: Building an Incident Response Playbook
description: Practitioner guide to writing actionable incident-response playbooks that define roles, escalation, and step-by-step handling procedures.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, operations]
version: 1.0.0
---
## Purpose
A playbook turns incident response from improvisation into repeatable process. This guide builds playbooks that define preparation, detection and analysis, containment, eradication, recovery, and lessons learned -- with named roles, decision points, and communication templates -- so the team acts coherently under pressure.

## When to use
- Creating the organization's first formal incident-response capability.
- Replacing vague policy documents with executable procedures.
- Preparing for specific threat scenarios (ransomware, data breach, insider).
- Meeting regulatory or contractual requirements for documented IR processes.

## Prerequisites
- Executive sponsorship and defined authority to isolate systems and engage third parties.
- Inventory of critical assets, data flows, and third-party dependencies.
- Contact lists: internal stakeholders, legal, PR, law enforcement, insurers.
- Communication channels that survive the compromise of primary systems.

## Procedure
1. Establish governance. Name the incident commander role, the core response team, and who can authorize disruptive actions such as network isolation.
2. Define severity levels and escalation. Write clear criteria for each severity, who is notified at each level, and the expected response times.
3. Write scenario playbooks. For each priority scenario, document detection sources, triage questions, containment options, eradication steps, and recovery criteria.
4. Build communication templates. Draft notification templates for executives, customers, regulators, and law enforcement, with legal review.
5. Define evidence handling. Specify collection procedures, storage locations, and chain-of-custody requirements from the start.
6. Integrate third parties. Document when and how to engage retainer firms, insurers, and law enforcement; keep contracts and contact details current.
7. Train and exercise. Run tabletop exercises at least annually and functional exercises for the core team; update the playbook after each.
8. Maintain the document. Assign an owner, version the playbook, and review it quarterly or after every significant incident.

## Expected outputs
- Versioned incident-response playbook with roles, severity matrix, and scenario procedures.
- Communication templates reviewed by legal.
- Exercise schedule and post-exercise improvement backlog.

## Pitfalls
- Playbooks that nobody exercises are fiction; test them before you need them.
- Missing authority to act turns the playbook into a suggestion during a real crisis.
- Overly rigid step-by-step scripts break on novel attacks; include decision principles too.
- Contact lists decay fast; verify them on every review cycle.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- ISO/IEC 27035, Information security incident management
- CISA incident response playbook resources
