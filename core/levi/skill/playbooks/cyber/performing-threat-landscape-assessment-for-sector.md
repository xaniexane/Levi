---
skill_id: cyber_performing_threat_landscape_assessment_for_sector
name: Threat Landscape Assessment for Sector
description: Assess the sector-specific threat landscape to focus defenses on the actors and techniques that matter most.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, landscape, strategy]
version: 1.0.0
---

## Purpose
- Focus security investment on the threats that actually target the organization's sector.
- Give leadership a clear picture of who attacks peers and how.
- Drive threat-informed defense: controls mapped to real adversary behavior.

## When to use
- Annually as input to security strategy and budgeting.
- When entering a new sector, geography, or market that changes the threat profile.
- After major sector incidents, to reassess exposure.
- When boards or regulators ask how the threat picture shapes the security program.

## Prerequisites
- Threat-intel sources covering the sector: ISAC feeds, vendor reports, and government advisories.
- Knowledge of the organization's crown jewels and attack surface.
- An ATT&CK-mapped view of current defensive coverage.
- Stakeholder access to validate business context.

## Procedure
1. Define scope: the sector, sub-sectors, and geographies relevant to the organization.
2. Collect intelligence on threat actors targeting the sector: motivations, capabilities, and typical initial access.
3. Map observed techniques to ATT&CK and compare against the organization's detection coverage.
4. Assess ransomware and extortion trends affecting sector peers.
5. Review supply-chain and third-party attack patterns in the sector.
6. Evaluate geopolitical and economic drivers that could shift targeting.
7. Identify the top five threats with rationale: likelihood, impact, and current defensive posture.
8. Recommend control improvements tied directly to the identified threats.
9. Present findings to leadership in business-risk language with clear asks.
10. Publish a sanitized version for wider staff awareness.
11. Set a refresh cadence and triggers for out-of-cycle updates.
12. Feed the assessment into risk registers, hunt planning, and purple team scenarios.

## Expected outputs
- A sector threat landscape report with top threats and rationale.
- ATT&CK-mapped gaps with control recommendations.
- Executive and staff-facing briefing materials.
- A one-page threat brief suitable for board reporting.
- Mapped detection use cases prioritized from the top threats.

## Pitfalls
- Copying generic global threat reports without sector filtering; relevance is everything.
- Presenting actor names without connecting them to defensive actions.
- Letting the assessment go stale; landscapes shift with geopolitics and economics.
- Treating the landscape as static; refresh after major sector incidents.

## References
- World Economic Forum Global Cybersecurity Outlook for macro context
- CISA sector-specific guidance and alerts
- ENISA threat landscape reports
- Verizon Data Breach Investigations Report for sector patterns
- MITRE ATT&CK for technique mapping, https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
