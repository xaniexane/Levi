---
skill_id: cyber_conducting_full_scope_red_team_engagement
name: Planning and Governing Full-Scope Red Team Engagements
description: Practitioner guide to scoping, authorizing, executing, and learning from full-scope adversary-emulation engagements.
risk: info
permissions: []
requires_confirmation: false
tags: [red-team, governance, assessment]
version: 1.0.0
---
## Purpose
A full-scope red team engagement emulates a real adversary across the kill chain -- but without rigorous governance it becomes either a stunt or a liability. This playbook covers the management side: defining objectives, writing rules of engagement, coordinating with defenders, controlling risk during execution, and converting findings into lasting improvement.

## When to use
- Commissioning your first full-scope red team exercise.
- Maturing ad-hoc pentests into adversary-emulation programs.
- Ensuring legal, safety, and operational risks are controlled during testing.
- Extracting maximum defensive value from engagement findings.

## Prerequisites
- Executive sponsorship and written authorization with defined scope.
- Legal review of rules of engagement, especially for social engineering and physical aspects.
- Trusted-agent structure: who knows about the engagement on the blue side.
- Incident-response integration so real incidents are not confused with the exercise.

## Procedure
1. Define objectives. State what the engagement must answer (for example, can an external attacker reach crown-jewel data?) rather than just "test security."
2. Write the rules of engagement. Document in-scope targets, prohibited actions, testing windows, data-handling rules, and emergency stop procedures; get signatures.
3. Establish trusted agents and communications. Define the secure channel between red team leads and trusted defenders, plus the duress and stop codes.
4. Plan the scenario. Design adversary emulation around relevant threat actors and TTPs; align with MITRE ATT&CK for coverage tracking.
5. Execute with control. Run in phases with check-ins; the trusted agent monitors for unintended impact and can pause the engagement.
6. Coordinate with blue team appropriately. Decide in advance what is blind versus informed; ensure SOC can distinguish exercise from real incidents via pre-shared indicators.
7. Debrief thoroughly. Walk defenders through every step, successful and failed; capture what detections fired, what missed, and why.
8. Convert to improvement. Turn findings into detection rules, hardening tasks, and process changes with owners and deadlines; retest the critical paths.

## Expected outputs
- Signed rules of engagement and engagement plan.
- Debrief report with ATT&CK-mapped findings.
- Remediation and detection-improvement backlog with owners.

## Pitfalls
- Vague scope leads to either timid testing or dangerous overreach; be specific.
- No emergency-stop procedure risks real operational damage.
- Blue team confusing the exercise with a real incident wastes IR resources; pre-coordinate.
- Reports that sit unread; the value is in the remediation, not the document.

## References
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- MITRE ATT&CK for adversary emulation planning
- CISA red-team and assessment guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
