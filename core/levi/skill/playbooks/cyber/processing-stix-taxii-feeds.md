---
skill_id: cyber_processing_stix_taxii_feeds
name: Processing STIX/TAXII Threat Intelligence Feeds
description: Ingest, validate, deduplicate, and operationalize STIX 2.1 objects from TAXII 2.1 feeds into detections.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, stix, taxii]
version: 1.0.0
---
## Purpose
Threat feeds are only useful when their indicators become detections, hunts, or blocks. This playbook covers the pipeline for STIX 2.1 content delivered over TAXII 2.1: collection, validation, deduplication, enrichment, conversion into platform detections, and lifecycle expiry so stale indicators do not linger.

## When to use
- Onboarding a new commercial or community threat feed.
- Building or maturing a threat intelligence platform (TIP) pipeline.
- When detection teams complain about stale or noisy feed indicators.
- Auditing which feeds actually produce true-positive detections.

## Prerequisites
- TAXII 2.1 client or TIP with collection credentials and polling schedule.
- Schema validation tooling for STIX 2.1 objects.
- Target platforms for output: SIEM, EDR, firewall, or DNS filter with APIs.
- Feed evaluation criteria: relevance, timeliness, accuracy, and license terms.

## Procedure
1. Configure TAXII collections per feed; authenticate and verify the first poll returns valid STIX 2.1 bundles.
2. Validate objects against the STIX 2.1 schema; quarantine malformed objects and notify the provider.
3. Deduplicate indicators across feeds by pattern and value; keep provenance (which feed, first seen).
4. Enrich with internal context: have we seen this indicator, on which assets, and was it malicious here.
5. Convert to platform content: Sigma rules, SIEM watchlists, EDR IOC lists, or firewall/DNS blocks, tagged with confidence and TLP.
6. Set expiry per indicator type (IPs and domains decay fast; hashes last longer) and auto-retire stale entries.
7. Measure per-feed precision: true positives divided by total alerts, and tune or drop poor feeds.
8. Document handling under TLP markings; never share TLP:RED or provider-restricted content externally.
9. Tag converted detections with source feed and TLP marking so analysts can trace provenance.
10. Validate STIX patterns, not just object schemas; pattern syntax errors silently drop indicators.
11. Run a monthly feed overlap analysis to consolidate redundant subscriptions.

## Expected outputs
- Operational pipeline: TAXII poll to detection/blocklist with provenance.
- Per-feed quality metrics (precision, volume, timeliness).
- Expired-indicator audit log proving lifecycle management.
- Provenance-tagged detection content (feed, TLP, first seen).
- Feed overlap and redundancy analysis.
- Pattern-validation log for ingested indicators.

## Pitfalls
- Feeding raw indicators straight to blocking causes outages; stage through alerting first.
- Ignoring TLP markings can breach sharing agreements and provider trust.
- No expiry policy means blocklists grow until they degrade performance and cause false positives.
- Free feeds vary wildly in quality; measure before trusting.
- STIX patterning errors fail silently; validate patterns independently of schema checks.
- Paying for multiple feeds with 90% overlap wastes budget; measure uniqueness.
- Indicator confidence from feeds is often inflated; calibrate with your own true-positive data.
- Bi-directional sharing obligations in ISAC memberships are easy to forget; contribute sightings back, not just consume.

## References
- OASIS STIX 2.1 and TAXII 2.1 specifications.
- MISP Project documentation (threat sharing platform).
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
