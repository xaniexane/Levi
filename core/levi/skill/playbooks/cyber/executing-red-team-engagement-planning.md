---
skill_id: cyber_executing_red_team_engagement_planning
name: Executing Red Team Engagement Planning
description: Plan a red-team engagement: objectives, scope, rules of engagement, and safety.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, planning, governance]
version: 1.0.0
---
## Purpose

A red-team engagement without rigorous planning is either ineffective (too constrained to find anything) or dangerous (outages, data exposure, legal liability). This playbook covers the planning phase: defining objectives tied to defensive improvement, scoping precisely, writing rules of engagement, and establishing safety and communication protocols — before anyone touches a keyboard offensively.

## When to use

- Leadership approved a red-team engagement and planning begins.
- You need a rules-of-engagement template for red-team work.
- A previous engagement had scope confusion or safety incidents.
- Procurement is evaluating red-team vendors and needs planning criteria.

## Prerequisites

- Stakeholders: executive sponsor, blue-team lead, IT/operations owners of in-scope systems, legal, HR.
- Threat-intel input: which adversary TTPs the engagement should emulate.
- Blue-team detection inventory (kept from the red team if testing detection).
- Planning artifacts: scoping questionnaire, ROE template, communication plan.

## Procedure

1. Define objectives tied to defensive improvement. Objectives should be specific and measurable: 'validate detection of credential-dumping and lateral movement in the finance segment' beats 'test our security.' Tie each objective to a defensive outcome (detection improvement, response-process validation) — engagements measured by 'flags captured' produce theater, not security.
2. Scope with precision. Document: in-scope networks/systems/accounts (by IP range, hostname, OU), explicitly out-of-scope systems (safety-critical, regulated, fragile), permitted techniques per phase, data-handling rules (what the team may access, exfiltrate as proof, and must never retain), and time windows (including blackout periods for business-critical operations). Ambiguous scope is the top cause of engagement incidents — write it down and get signatures.
3. Write rules of engagement covering: permitted and prohibited techniques (e.g., no ransomware detonation, no destructive payloads, no social engineering of specific groups without HR approval), pre-authorization for high-impact actions (domain compromise simulation, persistence), and the 'get out of jail' documentation operators carry. ROE is a legal and safety document — have legal review it.
4. Establish safety and communication protocols. Define: a 24/7 point of contact on both sides, codewords for pause/stop, escalation paths for unintended impact, daily check-ins during active operations, and shunning procedures (how the blue team stands down response to known red-team activity without blinding itself to real threats). Plan the reveal: when and how the blue team learns full details.
5. Plan for the blue team's benefit. Decide in advance: will this be red-team-known (testing response) or double-blind (testing detection)? What telemetry will be preserved for the debrief? Who writes the findings, and who owns the remediation? The engagement's value is realized in the debrief and the detection improvements — plan those deliverables now, not after.
6. Handle the administrative layer: contracts and liability (especially with external vendors), insurance, background checks for operators, data-retention and destruction terms for engagement artifacts, and HR/legal notification protocols. Unsexy, essential — the engagement that skips this is one incident away from a lawsuit.

## Expected outputs

- Objectives document: measurable, defense-tied, stakeholder-approved.
- Scope statement: in/out of scope, techniques, windows, data handling — signed.
- Rules of engagement: permitted/prohibited techniques, pre-authorization triggers, operator credentials.
- Safety/communications plan: contacts, pause/stop codewords, escalation, debrief plan.

## Pitfalls

- Vague scope ('the network') causes safety incidents — scope precisely and get signatures.
- Objectives measured in flags captured produce theater — tie to defensive improvement.
- Skipping legal review of ROE creates liability exposure for both sides.
- No pause/stop protocol means the first accident becomes a crisis — define it in advance.
- Planning the engagement but not the debrief/remediation wastes the findings — plan the full lifecycle.

## References

- NIST SP 800-115 (security testing: planning); CREST/industry red-team planning guidance; MITRE ATT&CK for adversary-emulation technique selection — https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
