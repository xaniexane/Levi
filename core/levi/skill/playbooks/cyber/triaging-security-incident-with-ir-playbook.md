---
skill_id: cyber_triaging_security_incident_with_ir_playbook
name: Triaging Security Incidents with an IR Playbook
description: Execute scenario-specific IR playbooks for consistent triage: roles, phases, communications, and evidence.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, playbook, soc]
version: 1.0.0
---
## Purpose
Generic triage gets you started; scenario playbooks get you finished consistently. This playbook covers using pre-built incident response playbooks (phishing, malware, ransomware, data breach, insider) during triage and response: following the phases, assigning roles, managing communications, and capturing evidence the same way every time.

## When to use
- Responding to an incident matching a defined scenario.
- Building or updating the organization's IR playbook library.
- Training responders through scenario walkthroughs.
- Auditing response consistency across incidents.

## Prerequisites
- Playbook library covering priority scenarios, kept current.
- Defined IR roles: commander, communications, technical leads.
- Communication channels (out-of-band) and stakeholder lists.
- Tooling access mapped per playbook (EDR, SIEM, forensics, containment).

## Procedure
1. Identify the scenario from triage indicators and open the matching playbook.
2. Assign roles immediately: incident commander, technical lead, communications, scribe.
3. Follow the playbook phases in order: detect/analyze, contain, eradicate, recover, lessons learned.
4. Execute the scenario's containment steps first (they are pre-approved for speed).
5. Work the evidence checklist: what to capture, in what order, with chain of custody.
6. Run communications on the playbook's cadence: internal updates, legal review, customer notifications.
7. Track deviations: when reality does not match the playbook, record why and what you did instead.
8. Close with the playbook's recovery criteria and schedule the lessons-learned review.
9. Version playbooks in git and require review on every change, like code.
10. Audit tool references in playbooks quarterly; decommissioned tools fail at 3 a.m.
11. Run at least one scenario exercise per quarter against the playbook library.

## Expected outputs
- Executed playbook with completed checklists and timestamps.
- Deviation log explaining departures from the playbook.
- Lessons-learned input for playbook updates.
- Version-controlled playbook repository with change history.
- Tool-reference audit results.
- Quarterly exercise schedule and results.

## Pitfalls
- A playbook nobody has read is decoration; exercise them regularly.
- Rigidly following a mismatched playbook wastes time; adapt and document deviations.
- Skipping communications steps creates the second incident: the messaging failure.
- Playbooks rot as tooling changes; review them after every tool or process change.
- Playbooks referencing decommissioned tools fail at 3 a.m.; audit tool references quarterly.
- Exercises that always succeed teach nothing; inject complications.
- Playbook metrics (time-to-contain) need baselines to show improvement; measure from the start.
- Playbook success metrics should include false-alarm handling, not just real incidents.

## References
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- CISA IR playbook resources.
- NIST SP 800-53 IR control family (for control mapping).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
