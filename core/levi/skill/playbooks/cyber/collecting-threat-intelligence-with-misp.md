---
skill_id: cyber_collecting_threat_intelligence_with_misp
name: Collecting Threat Intelligence with MISP
description: Practitioner guide to using MISP for structured collection, correlation, and distribution of threat intelligence.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, sharing, operations]
version: 1.0.0
---
## Purpose
MISP turns scattered threat data into structured, correlatable intelligence. This playbook covers using MISP as the collection hub: creating events, adding attributes and objects, leveraging galaxies and taxonomies, syncing with communities, and exporting to operational controls.

## When to use
- Standardizing how the team records threat intelligence.
- Participating in MISP-based sharing communities or ISACs.
- Correlating internal incident data with external feeds.
- Automating indicator distribution to detection and prevention tools.

## Prerequisites
- MISP instance with user accounts and role-based access.
- Defined taxonomies and tagging conventions for your team.
- Sharing groups and distribution rules aligned with TLP policy.
- Feed and sync connections configured or planned.

## Procedure
1. Define the event model. Decide what constitutes an event (incident, campaign, malware family) and the required fields for each.
2. Create events with context. Add a meaningful title, threat-level, analysis status, and description; link to the source investigation or report.
3. Add structured attributes. Record IOCs with correct types, categories, and to-ids flags (whether the attribute should trigger IDS); add context as tags.
4. Use objects and galaxies. Represent complex entities (files, registry keys, threat actors) with objects; tag with galaxies for actors, tools, and techniques.
5. Correlate. Review MISP's automatic correlations to find links between your events and community data; investigate meaningful overlaps.
6. Manage distribution. Set event distribution and sharing groups per TLP; verify nothing sensitive leaks to broader communities.
7. Sync and feed. Pull from trusted communities and feeds; push your shareable events outward on schedule.
8. Export to controls. Generate IDS rules, SIEM lookups, and blocklists from high-confidence attributes; automate the exports.

## Expected outputs
- Structured MISP events with consistent tagging and distribution.
- Community sync and feed ingestion operational.
- Automated exports feeding detection and prevention.

## Pitfalls
- Inconsistent attribute types and categories break correlation and exports.
- Wrong distribution settings leak sensitive events to public communities.
- to-ids flags set carelessly generate IDS noise or miss real detections.
- Events created without analysis status clutter the instance with half-finished data.

## References
- MISP project documentation and user guide
- FIRST Traffic Light Protocol (TLP) version 2.0
- OASIS STIX 2.1 specification (for export format context)
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
