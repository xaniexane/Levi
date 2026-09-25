---
skill_id: cyber_implementing_threat_modeling_with_mitre_attack
name: Implementing Threat Modeling with MITRE ATT&CK
description: Build adversary-informed threat models by mapping system attack surfaces to ATT&CK techniques.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-modeling, mitre-attack, risk-assessment]
version: 1.0.0
---
## Purpose
This playbook combines classic threat modeling (what are we building, what can go wrong) with MITRE ATT&CK (how real adversaries actually behave) to produce threat models that drive concrete detection and mitigation priorities.

## When to use
- Designing or reviewing a system, product, or cloud architecture.
- Prioritizing which ATT&CK techniques your detections must cover.
- Communicating risk to engineers in terms of concrete adversary actions.

## Prerequisites
- System documentation: architecture diagrams, data flows, trust boundaries, technology inventory.
- Relevant threat intelligence: which actor types target your sector and their known TTPs.
- Facilitator and participants from engineering, security, and product.

## Procedure
1. **Define scope and assets.** Decompose the system into components and data flows; identify crown-jewel assets and trust boundaries.
2. **Enumerate threats per component.** For each component, brainstorm using STRIDE or a similar mnemonic, then translate each threat into one or more ATT&CK techniques.
3. **Ground in real adversary behavior.** Pull CTI for your sector; for each relevant technique, note which actors use it and what mitigations and detections ATT&CK recommends.
4. **Score and prioritize.** Rate each threat by likelihood (adversary interest plus exposure) and impact; produce a ranked list, not an exhaustive one.
5. **Assign mitigations and detections.** For top threats, specify the control (preventive) and the detection (SIEM rule, EDR policy) with owners and deadlines.
6. **Record residual risk.** Document accepted risks with rationale and sign-off; a threat model that claims zero residual risk is not credible.
7. **Review on change.** Re-run the model when architecture, data flows, or the threat landscape change materially — at least annually.

8. **Link to detection engineering.** Every high-priority technique in the model should map to an existing detection or a backlog item; the model is incomplete until the coverage question is answered.
9. **Use the model in design reviews.** Make threat-model sign-off a gate for major architecture changes so new attack surface gets assessed before it ships.

## Expected outputs
- Threat model document: diagrams, per-component threats, ATT&CK technique mappings.
- Prioritized mitigation and detection backlog with owners.
- Residual risk register with acceptance records.
- Example: modeling a customer portal maps credential-stuffing (T1110.004) and session hijacking to the login flow, producing a rate-limiting requirement and a SIEM detection for anomalous session reuse.

## Pitfalls
- Modeling in a vacuum without CTI: you get theoretical threats nobody actually uses.
- Trying to cover every technique; focus on what fits your architecture and adversaries.
- Filing the model away; it must live next to the architecture docs and be maintained.

- Threat modeling only the happy path while attackers live in error handling, retries, and fallback logic; model failure modes explicitly.
- Assigning mitigations without owners or dates, which converts the threat model into a wish list.

## References
- MITRE ATT&CK (attack.mitre.org) — techniques, mitigations, detections.
- NIST SP 800-154, Guide to Data-Centric System Threat Modeling.
- OWASP Threat Modeling Cheat Sheet (cheatsheetseries.owasp.org) — practical process guidance.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
