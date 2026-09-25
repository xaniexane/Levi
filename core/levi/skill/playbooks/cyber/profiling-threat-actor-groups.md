---
skill_id: cyber_profiling_threat_actor_groups
name: Profiling Threat Actor Groups
description: Build structured threat actor profiles from TTPs, infrastructure, and victimology for defensive planning.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, actors, profiling]
version: 1.0.0
---
## Purpose
Threat actor profiling turns scattered reporting into a structured picture of who is targeting your sector, how they operate, and what to prioritize. This playbook covers collecting and fusing open and commercial reporting into actor profiles (motivation, capability, TTPs, infrastructure, victimology) used to drive detection engineering and defensive priorities. It is analytic work, not targeting of individuals.

## When to use
- Standing up or maturing a cyber threat intelligence function.
- After an incident where attribution would focus remediation and hunting.
- Sector-specific risk assessments (e.g. which ransomware affiliates target healthcare).
- Prioritizing detection engineering against the most relevant adversaries.

## Prerequisites
- Access to threat reporting: vendor blogs, CISA/NCSC advisories, ISAC feeds.
- MITRE ATT&CK navigator or equivalent for TTP mapping.
- Analytic standards for confidence levels and estimative language.
- A profile template (objectives, TTPs, infrastructure, victimology, gaps).

## Procedure
1. Define the intelligence requirement: which sector, region, or incident the profile must serve.
2. Collect reporting on the actor from multiple independent sources; record source reliability.
3. Extract TTPs and map them to MITRE ATT&CK techniques, noting which are consistently observed vs single-source.
4. Document infrastructure patterns: domain naming, hosting providers, certificate habits, and tooling.
5. Build victimology: targeted sectors, geographies, and company sizes, with dates to show evolution.
6. Apply the Diamond Model (adversary, capability, infrastructure, victim) to expose analytic gaps.
7. Assign confidence to each judgment and list collection gaps explicitly rather than filling them with assumption.
8. Publish the profile with defensive recommendations: which detections, hunts, and controls map to this actor's TTPs.
9. Review and refresh on a schedule or when new reporting contradicts the profile.
10. Map the actor's TTPs against your detection coverage to expose blind spots.
11. Track the actor's infrastructure reuse over time as an early warning of renewed campaigns.
12. Brief detection engineers directly; profiles that stay in intel reports do not become detections.

## Expected outputs
- Structured actor profile with TTP mapping, infrastructure, and victimology.
- ATT&CK heatmap showing the actor's technique coverage vs your detection coverage.
- Prioritized defensive recommendations tied to the actor's observed behavior.
- Detection-coverage gap analysis mapped to the actor's TTPs.
- Infrastructure watchlist for early-warning monitoring.
- Detection-engineering backlog derived from the profile.

## Pitfalls
- Single-source attribution is fragile; require corroboration before acting on identity claims.
- Actor names vary across vendors (one group, many aliases); maintain an alias map.
- TTPs evolve faster than profiles; stale profiles misdirect detection engineering.
- Attribution debates can stall response; keep profiling parallel to, not blocking, containment.
- Public reporting lags operations by months; treat profiles as trailing indicators.
- Over-fitting defenses to one actor leaves gaps against others; balance with baseline controls.
- Sharing profiles externally requires sanitization of sources and methods.

## References
- MITRE ATT&CK Groups knowledge base (attack.mitre.org/groups).
- CISA and NCSC joint cybersecurity advisories.
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
