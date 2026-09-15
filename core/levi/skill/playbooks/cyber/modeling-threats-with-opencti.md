---
skill_id: cyber_modeling_threats_with_opencti
name: Modeling Threats with OpenCTI
description: Build and maintain structured threat models and knowledge graphs in OpenCTI.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intelligence, opencti, threat-modeling]
version: 1.0.0
---
## Purpose
This playbook uses OpenCTI as the system of record for threat knowledge: modeling threat actors, campaigns, intrusion sets, and their TTPs as STIX 2.1 objects, and using the resulting graph to drive detection and hunting priorities.

## When to use
- Threat intel lives in disconnected reports and analysts' heads.
- You need to answer "which actors target us, how, and what are we missing."
- Correlating internal sightings with external reporting over time.

## Prerequisites
- OpenCTI deployed with connectors for your feeds (TAXII, MISP, commercial).
- Agreed data model conventions: naming, confidence scales, TLP handling.
- Analyst time protected for curation; a knowledge base without gardeners becomes a weed patch.

## Procedure
1. **Define the model scope.** Decide which entity types you maintain authoritatively (threat actors, intrusion sets, campaigns, malware, vulnerabilities) vs. consume from feeds.
2. **Ingest and deduplicate.** Connect feeds via TAXII/connectors; merge duplicate entities and resolve conflicts with documented confidence rationale.
3. **Model your priority actors.** For each relevant actor, build the full picture: attributed campaigns, malware, infrastructure, and ATT&CK-mapped TTPs with source references.
4. **Record internal sightings.** Link your own detections and incidents to the modeled entities; internal sightings are the highest-value data in the graph.
5. **Derive detection requirements.** For each priority actor, list TTPs with no corresponding detection and file them as detection-engineering backlog items.
6. **Produce from the graph.** Generate actor profiles, campaign timelines, and briefing graphics directly from OpenCTI rather than maintaining parallel slide decks.
7. **Curate continuously.** Review entity confidence quarterly, archive stale campaigns, and audit for orphaned or contradictory relationships.

8. **Automate enrichment.** Use connectors and playbooks to auto-enrich new observables with passive DNS, WHOIS, and sandbox verdicts so analysts start from context, not raw strings.
9. **Back up the knowledge base.** The curated graph is an organizational asset; back it up and test restoration like any critical system.

## Expected outputs
- Curated threat knowledge graph with priority actors fully modeled.
- Detection backlog derived from TTP coverage gaps.
- Repeatable reporting generated from the platform.
- Example: an intrusion set entity links three campaigns, two malware families, and 14 ATT&CK techniques; the graph view immediately shows which techniques lack detections, prioritized for the next detection sprint.

## Pitfalls
- Ingesting everything and curating nothing: a big graph with no judgments.
- Modeling actors you will never defend against while neglecting the ones targeting you.
- Treating confidence as decoration instead of recording why you believe each assertion.

- Modeling with no connection to detection engineering; a beautiful graph that generates no detections is a hobby, not a capability.
- Importing threat reports as flat text instead of structured objects; unparsed reports do not participate in correlation.

## References
- OpenCTI documentation (docs.opencti.io).
- OASIS STIX 2.1 specification (docs.oasis-open.org/cti/stix/v2.1).
- Filigran OpenCTI connectors repository (github.com/OpenCTI-Platform/connectors) — ingestion options.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
