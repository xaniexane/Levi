---
skill_id: cyber_investigating_insider_threat_indicators
name: Investigating Insider Threat Indicators
description: Investigate potential insider threat activity lawfully, discreetly, and with proper oversight.
risk: low
permissions: []
requires_confirmation: false
tags: [insider-threat, investigations, uebe]
version: 1.0.0
---
## Purpose
This playbook guides a lawful, discreet investigation of insider-threat indicators: validating the signal, gathering evidence with proper authorization, and coordinating HR and legal — protecting both the organization and the rights of the individual.

## When to use
- UEBA/DLP alerts or tips suggest data theft, sabotage, or fraud by an insider.
- An employee with elevated access resigns under contentious circumstances.
- Auditors ask how insider-risk cases are handled.

## Prerequisites
- An insider-threat program charter defining who can authorize investigations (legal, HR, security leadership).
- Legal counsel involved before any monitoring beyond normal business operations begins.
- Evidence-handling procedures: chain of custody, access control, retention.

## Procedure
1. **Validate the trigger.** Confirm the alert is not a benign explanation (role change, approved project, misconfigured rule) before escalating to a formal case.
2. **Get authorization.** Open a case only with documented approval from the designated authority; record scope, data sources approved, and time bounds.
3. **Preserve evidence quietly.** Collect relevant logs (access, DLP, email metadata per policy, endpoint telemetry) with hashes and timestamps; avoid alerting the subject through clumsy collection.
4. **Correlate behavior.** Build a timeline: access anomalies, data movement, policy violations, and HR context (performance actions, resignation); look for the convergence of motive, means, and opportunity indicators.
5. **Involve HR and legal early.** Share findings through the defined channel; let HR/legal own employment decisions while security owns the technical facts.
6. **Contain proportionate to risk.** Options range from enhanced monitoring to access revocation to coordinated separation; choose based on evidence strength and ongoing risk, with legal sign-off.
7. **Close with documentation.** Write the case report: allegations, evidence, conclusions, actions taken; retain per policy and feed lessons into controls (e.g., DLP tuning, offboarding checks).

8. **Protect the investigators.** Limit case knowledge to need-to-know, log all access to case materials, and provide a clear escalation path if the subject is in the security team itself.
9. **Measure program health.** Track time from trigger to disposition and the rate of substantiated vs. unsubstantiated cases; a healthy program investigates quickly and fairly.

## Expected outputs
- Authorized case file with evidence inventory and chain of custody.
- Timeline correlating technical indicators with HR context.
- Control improvements (monitoring, offboarding, access reviews) from lessons learned.
- Example: a DLP alert on mass downloads by a departing engineer is validated, authorized for investigation, and resolved with evidence showing approved project archival — documented and closed without employment action.

## Pitfalls
- Investigating without legal/HR authorization: evidence may be unusable and the company exposed.
- Tipping off the subject through visible collection, destroying evidence or escalating behavior.
- Confirmation bias: build the timeline first, then assess — do not start from a conclusion.

- Expanding the investigation scope without fresh authorization because "we were already looking"; scope creep destroys the legal defensibility of the case.
- Relying solely on technical indicators while ignoring the human context; most insider cases are resolved by understanding motive, not by finding more logs.

## References
- CISA Insider Threat Mitigation Guide (cisa.gov/insider-threat-mitigation).
- NIST SP 800-53 Rev. 5, control family PS and IR guidance on personnel-related incidents.
- CERT Insider Threat Center research (sei.cmu.edu) — insider threat patterns and mitigations.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
