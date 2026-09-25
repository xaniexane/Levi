---
skill_id: cyber_performing_soc_tabletop_exercise
name: SOC Tabletop Exercise
description: Exercise SOC analysts, processes, and playbooks with realistic incident scenarios in a discussion-based format.
risk: info
permissions: []
requires_confirmation: false
tags: [soc, tabletop, preparedness]
version: 1.0.0
---

## Purpose
- Test whether SOC playbooks work when real people follow them under time pressure.
- Find gaps in tooling, access, and escalation paths before a real incident exposes them.
- Build analyst confidence and cross-shift coordination.

## When to use
- Quarterly as part of SOC readiness, or after significant tooling or staffing changes.
- When new playbooks are published, to validate them before they are needed.
- After real incidents, to rehearse the scenarios that caused trouble.
- When onboarding new analysts to teach process alongside tools.

## Prerequisites
- A facilitator with SOC experience and realistic scenario injects.
- Current playbooks, escalation matrices, and contact lists.
- Participation from analysts across shifts plus SOC leadership.
- A blameless ground rule: the exercise tests the process, not the people.

## Procedure
1. Choose a scenario relevant to current threats: ransomware, business email compromise, insider activity, or cloud breach.
2. Define objectives: which playbooks and handoffs are under test.
3. Prepare injects that escalate realistically: initial alert, contradictory data, executive pressure, and tool outages.
4. Brief participants on the scenario start state and the ground rules.
5. Walk through triage: how the alert is picked up, enriched, and prioritized.
6. Exercise escalation: when does this become an incident, who declares it, and who gets called.
7. Test containment decisions: what can the SOC isolate without approval, and where does authority sit.
8. Inject complications: a key tool is down, the on-call engineer is unreachable, evidence is contradictory.
9. Discuss communications: internal updates, stakeholder notifications, and documentation during the incident.
10. Capture gaps in real time: missing runbook steps, access analysts lack, and unclear decision rights.
11. Assign owners and deadlines for every gap found.
12. Update playbooks with the lessons and schedule the next exercise.

## Expected outputs
- A gap register with owners and deadlines.
- Updated SOC playbooks reflecting lessons learned.
- Analysts practiced in escalation and communication under pressure.
- A maturity score tracking SOC readiness across exercises.
- Cross-training plans so no playbook depends on a single analyst.

## Pitfalls
- Making the scenario too easy; inject the ambiguity and tool failures of real incidents.
- Exercising only day-shift staff; incidents do not respect business hours.
- Treating the exercise as a test of individuals rather than of process and tooling.
- Running exercises only when things are calm; readiness matters most before change freezes.

## References
- CISA Cyber Security Evaluation Tool (CSET) for capability mapping
- NIST SP 800-61 Incident Handling Guide
- NIST SP 800-84 Guide to Test, Training, and Exercise Programs
- SANS SOC skills assessment resources
- CISA tabletop exercise packages
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
