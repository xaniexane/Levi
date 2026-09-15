---
skill_id: cyber_building_threat_feed_aggregation_with_misp
name: Building Threat Feed Aggregation with MISP
description: Practitioner guide to aggregating, correlating, and operationalizing threat feeds using the MISP platform.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, sharing, automation]
version: 1.0.0
---
## Purpose
Security teams subscribe to many feeds but act on few. This playbook uses MISP (Malware Information Sharing Platform) to aggregate feeds, deduplicate and correlate indicators, and push actionable intelligence to detection and prevention controls -- turning feed sprawl into a managed pipeline.

## When to use
- Consolidating multiple commercial and open-source threat feeds.
- Sharing indicators with trusted communities via MISP sync.
- Automating the path from feed ingestion to SIEM and firewall rules.
- Replacing spreadsheet-based IOC tracking.

## Prerequisites
- MISP deployment with storage sized for feed volume.
- Feed subscriptions with documented licensing and distribution rules.
- Defined confidence and aging policies for indicators.
- Export targets: SIEM, EDR, firewall, or DNS filtering.

## Procedure
1. Deploy and secure MISP. Install the platform, enable authentication, and configure organizations, sharing groups, and TLP handling.
2. Connect feeds deliberately. Add feeds that match your threat model; record each feed's licensing, update cadence, and distribution permissions.
3. Normalize and deduplicate. Let MISP correlate overlapping indicators; configure correlation to avoid drowning in duplicates.
4. Set confidence and decay. Apply sighting-based confidence and time-decay so stale or unconfirmed indicators age out automatically.
5. Build distribution rules. Define which tags and confidence levels sync to each community and which export to internal controls.
6. Automate exports. Push high-confidence indicators to the SIEM, EDR, or blocking controls on a schedule; log what was exported.
7. Monitor feed health. Track ingestion volume, correlation rates, and false positives per feed; drop or renegotiate poor performers.
8. Review quarterly. Audit sharing-group memberships, distribution rules, and feed relevance against the current threat landscape.

## Expected outputs
- Operational MISP instance with curated feeds and correlation.
- Automated exports to detection and prevention controls.
- Feed quality metrics and quarterly review process.

## Pitfalls
- Subscribing to every available feed creates noise that buries the good intelligence.
- Exporting unvetted indicators to blocking controls causes outages.
- Ignoring distribution licensing violates sharing agreements and trust.
- Stale indicators without decay accumulate into unmanageable blocklists.

## References
- MISP project documentation
- FIRST Traffic Light Protocol (TLP) version 2.0
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- OASIS STIX 2.1 specification (for feed format context)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
