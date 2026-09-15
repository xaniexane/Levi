---
skill_id: cyber_implementing_stix_taxii_feed_integration
name: Implementing STIX/TAXII Feed Integration
description: Ingest and operationalize STIX/TAXII threat intelligence feeds into security tooling.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intelligence, stix, taxii]
version: 1.0.0
---
## Purpose
This playbook explains how to connect STIX/TAXII feeds to your detection and response stack: selecting feeds, normalizing the data, scoring it, and pushing actionable indicators to enforcement points without drowning analysts in noise.

## When to use
- Threat intelligence arrives as emailed PDFs or manual lookups and never reaches controls.
- You need machine-readable sharing with partners, ISACs, or internal teams.
- Detection content should be enriched automatically with actor, campaign, and TTP context.

## Prerequisites
- A threat intelligence platform (MISP, OpenCTI, or commercial TIP) that speaks STIX 2.1/TAXII 2.1.
- Feed inventory: commercial, open-source, government, and industry-sharing sources with access credentials.
- Defined confidence and relevance scoring criteria before ingestion begins.

## Procedure
1. **Catalog and vet feeds.** Record each feed's scope, update cadence, format, licensing, and historical precision; drop feeds that duplicate higher-quality sources.
2. **Connect via TAXII collections.** Configure polling with authentication, validate the server certificate, and confirm the STIX version negotiated.
3. **Normalize on ingest.** Map objects to your internal model (indicator types, kill-chain phases, ATT&CK techniques) and deduplicate against existing holdings.
4. **Score and expire.** Apply confidence, relevance to your sector, and freshness scoring; set TTLs per indicator type (hours for IPs, months for file hashes with context).
5. **Distribute to controls.** Push high-confidence indicators to the SIEM, EDR, firewall, DNS, and email gateway with feed-tagged rules so you can trace every block to its source.
6. **Close the loop.** Track which feed-sourced indicators actually fired in your environment and feed precision metrics back into feed selection and scoring weights.
7. **Handle sharing markings.** Respect TLP and any distribution controls; automate downgrading or stripping fields when sharing outside the original audience.

## Expected outputs
- Documented feed catalog with scoring weights and TTL policy.
- Automated pipeline from TAXII poll to control enforcement with provenance tags.
- Metrics: indicator precision per feed, time from publish to enforcement, analyst enrichment usage.

## Pitfalls
- Ingesting every available feed: volume without scoring creates alert fatigue.
- Never expiring indicators: stale blocks cause false positives and business disruption.
- Ignoring TLP markings, which can breach sharing agreements and partner trust.

## References
- OASIS STIX 2.1 and TAXII 2.1 specifications (oasis-open.org; docs.oasis-open.org/cti).
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
