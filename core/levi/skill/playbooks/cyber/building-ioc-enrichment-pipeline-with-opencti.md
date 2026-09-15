---
skill_id: cyber_building_ioc_enrichment_pipeline_with_opencti
name: Building an IOC Enrichment Pipeline with OpenCTI
description: Practitioner guide to deploying OpenCTI and wiring enrichment connectors so raw indicators become contextualized threat intelligence.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, automation]
version: 1.0.0
---
## Purpose
Raw indicators are low-value without context: who uses them, what malware they belong to, how confident the attribution is. This playbook deploys the OpenCTI threat-intelligence platform and configures enrichment connectors so that ingested IOCs are automatically correlated with threat actors, campaigns, and vulnerabilities.

## When to use
- Standing up a threat-intelligence capability that goes beyond flat IOC lists.
- Consolidating feeds, incident artifacts, and OSINT into one knowledge graph.
- Automating enrichment so analysts spend time on judgments, not lookups.
- Feeding enriched intelligence into detection engineering and hunting.

## Prerequisites
- Infrastructure for OpenCTI (containers or VMs) with persistent storage.
- API keys for enrichment sources (abuse databases, passive DNS, sandbox services).
- Threat feeds to ingest, with licensing and TLP handling understood.
- Analysts familiar with the STIX 2.1 data model concepts.

## Procedure
1. Deploy OpenCTI. Install the platform with its dependencies, secure the admin interface, and configure authentication and role-based access.
2. Define the data model usage. Decide how your team represents incidents, malware, actors, and infrastructure in STIX objects; document naming conventions.
3. Connect ingestion feeds. Add internal feeds (incident IOCs) and external feeds; set confidence thresholds and TLP handling per feed.
4. Enable enrichment connectors. Configure connectors for passive DNS, WHOIS, sandbox detonation, and reputation lookups so new indicators enrich automatically.
5. Build correlation rules. Define how OpenCTI links indicators to campaigns and actors; review auto-created relationships for quality.
6. Integrate with operations. Push high-confidence indicators to the SIEM, firewall, or EDR via export connectors; document the sync cadence.
7. Tune and deduplicate. Resolve duplicate entities, adjust connector polling, and prune low-value feeds quarterly.
8. Train analysts. Ensure the team can pivot the knowledge graph, write investigations in the platform, and export intelligence products.

## Expected outputs
- Operational OpenCTI instance with ingestion and enrichment connectors.
- Documented data-model conventions and TLP handling rules.
- Automated exports feeding detection and prevention controls.

## Pitfalls
- Enabling every available connector overwhelms analysts with low-value relationships.
- Poor STIX hygiene (duplicate entities, inconsistent names) degrades the knowledge graph.
- Exporting unvetted indicators to blocking controls causes false-positive outages.
- Ignoring API rate limits of enrichment sources leads to throttled or billed surprises.

## References
- OpenCTI project documentation
- OASIS STIX 2.1 and TAXII 2.1 specifications
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- MITRE ATT&CK for threat-actor and technique correlation
