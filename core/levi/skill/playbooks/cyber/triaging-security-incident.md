---
skill_id: cyber_triaging_security_incident
name: Triaging a Security Incident
description: Initial incident triage: assess severity, scope the impact, decide containment, and engage the right teams.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, triage, soc]
version: 1.0.0
---
## Purpose
The first hour of an incident determines its trajectory. This playbook defines initial triage: quickly assessing severity and scope from the available signals, making the containment decision, engaging the right teams, and preserving evidence, before the full investigation begins.

## When to use
- A security alert is suspected to be a real incident.
- User or third-party reports of compromise.
- Automated detection fires with unclear scope.
- Any event requiring a go/no-go on incident declaration.

## Prerequisites
- Incident severity matrix and declaration criteria.
- Contact lists: IR team, IT operations, legal, communications, executives.
- Access to core telemetry: EDR, SIEM, identity, network logs.
- Evidence preservation capability (do not destroy logs or reimage yet).

## Procedure
1. Capture the initial report: who, what, when, and which systems are implicated; start a timeline immediately.
2. Assess severity using the matrix: data involved, system criticality, active vs historical, and spread indicators.
3. Scope quickly: which hosts, accounts, and data are affected; assume wider until evidence narrows it.
4. Decide containment: isolate hosts, disable accounts, or block indicators, balancing business impact.
5. Preserve evidence: snapshot, capture memory/disk images of key systems before remediation actions.
6. Engage the right teams per severity: IR lead, IT, legal, comms; notify leadership on a defined cadence.
7. Declare the incident formally if criteria are met; open the incident record and assign roles.
8. Hand off to investigation with the triage package: timeline, scope, actions taken, and open questions.
9. Establish a war-room channel template so the first 15 minutes are not spent on logistics.
10. Assign the scribe role first; decisions made without notes are lost.
11. Define explicit criteria for escalating from triage to full incident declaration.

## Expected outputs
- Triage record: severity, scope assessment, and declaration decision.
- Initial timeline and evidence inventory.
- Containment actions log and engaged-stakeholder list.
- War-room template and channel-naming standard.
- Triage decision log with timestamps.
- Escalation criteria documentation.

## Pitfalls
- Reimaging or 'fixing' before evidence capture destroys the investigation.
- Under-scoping early is the classic error; validate the boundary with data, not hope.
- Delayed containment for business convenience lets ransomware and worms spread.
- Poor notes during triage become poor timelines later; document as you go.
- Triage decisions made over chat without a scribe are lost; assign the scribe role first.
- Declaring too late wastes the containment window; bias toward early declaration.
- Single points of contact who are unreachable stall triage; maintain deputies.
- Triage bridges and war rooms need pre-provisioned access; onboarding during an incident wastes time.

## References
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- CISA Incident Response guidance.
- SANS Incident Handler's Handbook concepts.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
