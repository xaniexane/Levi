---
skill_id: cyber_performing_threat_modeling_with_owasp_threat_dragon
name: Threat Modeling with OWASP Threat Dragon
description: Model application threats with OWASP Threat Dragon to identify design flaws early in the lifecycle.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-modeling, appsec, design]
version: 1.0.0
---

## Purpose
- Find security design flaws before code is written, when fixes are cheapest.
- Give development teams a visual, collaborative way to reason about threats.
- Produce threat models that feed security requirements and test plans.

## When to use
- During design of new applications or major features.
- When changing trust boundaries: new integrations, data flows, or authentication schemes.
- As part of secure SDLC gates before implementation begins.
- After incidents, to model how the design allowed the failure.

## Prerequisites
- OWASP Threat Dragon installed or accessible, with templates for the diagram types used.
- Architecture documentation: components, data flows, and trust boundaries.
- Participants from development, architecture, and security.
- A threat-modeling methodology agreed in advance, such as STRIDE.

## Procedure
1. Define scope: which components and data flows are in the model and what is assumed secure.
2. Draw the data-flow diagram in Threat Dragon: processes, data stores, external entities, and trust boundaries.
3. Decompose to the right level: detailed enough to find flaws, simple enough to maintain.
4. Apply STRIDE per element: spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege.
5. Identify threats with concrete attack scenarios, not generic labels.
6. Rate each threat by impact and likelihood using an agreed scale.
7. Define mitigations: design changes, security controls, or accepted risks with rationale.
8. Assign owners and track mitigations like any other security requirement.
9. Review the model when the design changes; a stale model is worse than none.
10. Use the model to derive security test cases for QA and penetration testing.
11. Archive models with the project documentation for audit and future reference.
12. Measure the program: threats found per model and design flaws caught before code.

## Expected outputs
- Threat Dragon diagrams with documented threats, ratings, and mitigations.
- Security requirements and test cases derived from the model.
- Tracked mitigation owners and completion status.
- A threat-model review checklist for architecture review boards.
- Training materials so development teams can self-serve basic models.

## Pitfalls
- Modeling at the wrong granularity; too abstract finds nothing, too detailed never finishes.
- Running the session without developers; the people building it must own the threats.
- Filing the model away; it must live with the design and evolve with it.
- Modeling the happy path only; include abuse cases and failure modes.

## References
- OWASP Threat Modeling Cheat Sheet
- OWASP Threat Dragon documentation
- OWASP threat modeling guidance and STRIDE references
- NIST SP 800-218 Secure Software Development Framework
- Shostack's Threat Modeling: Designing for Security for methodology depth
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
