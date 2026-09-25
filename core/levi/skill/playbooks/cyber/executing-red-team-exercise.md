---
skill_id: cyber_executing_red_team_exercise
name: Executing Red Team Exercise
description: Execute an authorized red-team exercise safely with full defensive value capture.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, exercise, purple-team]
version: 1.0.0
---
## Purpose

Executing a red-team exercise means conducting authorized adversary emulation against production or production-like systems — real techniques, real impact potential. This playbook covers safe execution: phased operations, continuous safety monitoring, blue-team coordination, and capturing every finding for defensive improvement. It carries elevated risk and requires confirmation because these activities touch live systems by design.

## When to use

- A planned red-team engagement moves to execution phase.
- You are the exercise lead responsible for safe operations.
- Blue team needs coordination procedures during active red-team operations.
- Post-exercise: capturing findings for detection and response improvement.

## Prerequisites

- Signed rules of engagement, scope statement, and authorizations from the planning phase.
- Safety infrastructure: 24/7 contacts, pause/stop codewords, escalation paths, monitoring for unintended impact.
- Blue-team coordination plan: what the blue team knows, shunning procedures, deconfliction contacts.
- Evidence-capture plan: operator logs, telemetry preservation, timeline recording.

## Procedure

1. Confirm authorization and safety before starting. Verify: signed ROE and scope are in hand, all operators have their authorization documentation, safety contacts acknowledge readiness, monitoring for unintended impact is active, and the stop codeword is understood by everyone. Never begin execution on verbal approval — the paperwork is the safety system.
2. Execute in phases with checkpoints. Run the standard progression — reconnaissance, initial access, persistence, privilege escalation, lateral movement, actions on objectives — with a checkpoint between phases: confirm no unintended impact, confirm telemetry is being captured, and get phase authorization where ROE requires it. Phased execution with checkpoints is what separates exercises from incidents.
3. Maintain continuous safety monitoring. A dedicated safety observer (not an operator) watches for: impact outside scope, production degradation, data exposure beyond agreed limits, and operator deviation from ROE. Any safety trigger invokes pause immediately — investigate, document, and only resume with explicit re-authorization. Safety monitoring is non-negotiable, not overhead.
4. Coordinate with the blue team per the plan. Follow the agreed notification model (full-knowledge, partial, or double-blind), use deconfliction contacts before high-noise actions, and ensure the blue team's shunning procedures don't create real blind spots. If a real incident occurs during the exercise, the exercise pauses — real response takes absolute priority, communicated via the emergency channel.
5. Capture everything for the debrief. Operators log every action with timestamps; preserve all relevant telemetry; record which detections fired, which didn't, and analyst response actions. The exercise's product is not access achieved — it's the detection-and-response gap analysis. Incomplete operator logs make the debrief worthless.
6. Debrief with blameless rigor. Walk through the full timeline with blue team, purple-team style: for each technique, what was detected, what was missed, and why. Convert every miss into a detection-engineering ticket with an owner. Present findings to leadership as defensive improvements, not attacker triumphs. Schedule the re-test — the exercise's value is realized when the gaps close.

## Expected outputs

- Execution logs: operator actions with timestamps, phase checkpoints, safety-monitor records.
- Detection-gap analysis: per-technique detected/missed/partial with evidence.
- Blue-team coordination records: notifications, deconfliction, real-incident handling.
- Remediation backlog: detection tickets with owners, re-test schedule.

## Pitfalls

- Starting execution without signed ROE risks legal exposure and safety incidents — paperwork first.
- Skipping phase checkpoints lets small deviations become big impacts.
- Safety monitoring by the operators themselves is a conflict of interest — use a dedicated observer.
- A real incident during the exercise takes absolute priority — plan for it explicitly.
- Measuring success by access achieved instead of defensive improvement wastes the exercise.

## References

- NIST SP 800-115 (security testing: execution); MITRE ATT&CK for technique reference — https://attack.mitre.org/; Industry red-team execution standards (CREST, CBEST methodologies)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
