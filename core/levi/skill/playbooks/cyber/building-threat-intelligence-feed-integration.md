---
skill_id: cyber_building_threat_intelligence_feed_integration
name: Building Threat Intelligence Feed Integration
description: Practitioner guide to selecting, integrating, and governing threat-intelligence feeds across security controls.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, integration, operations]
version: 1.0.0
---
## Purpose
Feeds are only useful when they reach the controls that can act on them. This playbook covers the end-to-end integration lifecycle: selecting feeds against your threat model, normalizing and scoring indicators, pushing them to SIEM, EDR, firewall, and DNS controls, and continuously measuring feed value.

## When to use
- Operationalizing newly purchased or subscribed threat feeds.
- Consolidating overlapping feeds into a coherent pipeline.
- Automating indicator distribution to prevention and detection tools.
- Evaluating whether existing feeds justify their cost.

## Prerequisites
- Inventory of security controls that can consume indicators and their formats.
- Feed subscriptions with licensing, TLP, and redistribution terms documented.
- Normalization and scoring criteria agreed with stakeholders.
- Change process for updating blocking and alerting rules.

## Procedure
1. Map feeds to the threat model. For each candidate feed, document which actors, sectors, or malware families it covers and why you need it.
2. Establish ingestion. Use TAXII, API, or platform connectors; validate format, update cadence, and authentication.
3. Normalize indicators. Convert to a common schema (type, value, confidence, first/last seen, TLP); deduplicate across feeds.
4. Score and filter. Apply confidence thresholds and relevance rules; only high-confidence, relevant indicators reach automated controls.
5. Distribute to controls. Push to SIEM for alerting, EDR and firewall for blocking, DNS filtering for domain indicators; log every push.
6. Handle TLP and licensing. Ensure redistribution respects each feed's terms; segment internal versus shareable indicators.
7. Measure feed value. Track true-positive rate, unique detections contributed, and overlap between feeds; report per-feed ROI.
8. Govern continuously. Review the feed portfolio quarterly; retire feeds that duplicate others or never fire.

## Expected outputs
- Documented feed portfolio with threat-model mapping and licensing.
- Automated normalization, scoring, and distribution pipeline.
- Per-feed value metrics and quarterly governance review.

## Pitfalls
- Feeding raw, unscored indicators into blocking controls causes outages.
- Overlapping feeds without deduplication multiply noise and cost.
- Ignoring redistribution terms breaches contracts and sharing trust.
- Never measuring value lets expensive, useless feeds persist indefinitely.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- OASIS STIX 2.1 and TAXII 2.1 specifications
- FIRST Traffic Light Protocol (TLP) version 2.0
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
