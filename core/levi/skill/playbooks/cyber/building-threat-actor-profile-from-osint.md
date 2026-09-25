---
skill_id: cyber_building_threat_actor_profile_from_osint
name: Building Threat Actor Profiles from OSINT
description: Practitioner guide to researching and documenting threat-actor profiles using only open-source intelligence.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, osint, analysis]
version: 1.0.0
---
## Purpose
Knowing who might target you -- their motives, capabilities, and preferred techniques -- focuses defenses where they matter. This playbook builds structured threat-actor profiles from public reporting, industry sharing, and open sources, producing a living document the SOC and leadership can act on.

## When to use
- Prioritizing defenses against actors most likely to target your sector.
- Preparing executive or board briefings on the threat landscape.
- Informing threat-hunting hypotheses with actor-specific techniques.
- Onboarding analysts to the threats relevant to the organization.

## Prerequisites
- Access to reputable threat-intel reporting (vendor reports, government advisories, ISAC sharing).
- Framework for structuring profiles (for example, MITRE ATT&CK group pages as a template).
- Criteria for confidence levels and source reliability.
- Policy on handling unvetted or single-source claims.

## Procedure
1. Select the actors. Prioritize based on sector targeting, geography, and relevance to your technology stack; keep the list short enough to maintain.
2. Collect open sources. Gather vendor reports, government advisories, and reputable journalism; record source, date, and reliability for each claim.
3. Map techniques to ATT&CK. Translate reported behaviors into ATT&CK techniques and software; note which are confirmed versus suspected.
4. Document infrastructure and indicators. Record known domains, IPs, certificates, and malware families with first-seen and last-seen dates.
5. Assess motives and targeting. Summarize the actor's objectives (espionage, financial, disruption) and victimology relevant to your organization.
6. Rate confidence. Distinguish high-confidence facts from single-source claims; never present speculation as established.
7. Produce the profile. Write a concise document: overview, objectives, techniques, indicators, and defensive recommendations mapped to your controls.
8. Maintain the profile. Review quarterly or when significant new reporting appears; archive superseded claims with dates.

## Expected outputs
- Structured threat-actor profiles with ATT&CK mappings and confidence ratings.
- Defensive recommendations tied to existing controls and gaps.
- Review schedule and source-citation discipline.

## Pitfalls
- Single-source claims treated as fact corrupt downstream hunting and detection.
- Profiles that are never updated become misleading within months.
- Confusing actor aliases leads to fragmented or duplicated profiles.
- Collecting indicators without context produces unusable IOC dumps.

## References
- MITRE ATT&CK Groups knowledge base
- CISA advisories and joint cybersecurity advisories
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- Diamond Model of Intrusion Analysis (for structuring adversary data)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
