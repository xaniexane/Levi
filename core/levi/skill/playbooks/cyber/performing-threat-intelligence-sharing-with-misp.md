---
skill_id: cyber_performing_threat_intelligence_sharing_with_misp
name: Threat Intelligence Sharing with MISP
description: Operate MISP for threat intelligence collection, enrichment, and sharing with trusted communities.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intel, misp, sharing]
version: 1.0.0
---

## Purpose
- Centralize threat intelligence in MISP so the SOC, IR, and detection teams work from one source.
- Share indicators with trusted communities under proper handling rules.
- Automate the flow from MISP into detection and blocking controls.

## When to use
- When standing up or maturing a threat-intel program.
- When joining ISACs or sharing communities that use MISP as the exchange format.
- During incidents, to rapidly distribute IOCs internally and to partners.
- When automating IOC ingestion into SIEM, firewall, and EDR.

## Prerequisites
- A MISP instance deployed with appropriate access controls and backup.
- Defined sharing policies: TLP markings, distribution levels, and what may leave the organization.
- Feed sources: commercial, open-source, and community feeds relevant to the sector.
- Integration points: SIEM, TIP, firewalls, and EDR for automated consumption.

## Procedure
1. Deploy MISP with hardened configuration: TLS, authentication, and role-based access.
2. Define the taxonomy and tagging conventions the team will use consistently.
3. Connect trusted feeds and set sync rules; review feed quality before enabling automatic ingestion.
4. Establish sharing groups for each community with the correct distribution and TLP defaults.
5. Create events with full context: description, TLP, tags, sightings, and analyst notes, not bare IOCs.
6. Correlate incoming indicators against internal telemetry to find sightings before distributing.
7. Push validated IOCs to enforcement points: blocklists, SIEM watchlists, and EDR custom IOCs.
8. Set expiry on time-sensitive indicators so stale IOCs do not cause false positives.
9. Review sharing compliance regularly: no internal or personal data leaking into shared events.
10. Measure the program: feed precision, time from receipt to blocking, and sighting counts.
11. Contribute back to communities with sanitized sightings and original analysis.
12. Back up MISP data and test restoration; the intel platform is critical infrastructure.

## Expected outputs
- An operational MISP with feeds, sharing groups, and enforcement integrations.
- Context-rich events with sightings and expiry management.
- Program metrics showing intelligence value.
- A feed quality scorecard reviewed quarterly with underperforming feeds removed.
- Tabletop exercises using shared intelligence to validate the full workflow.

## Pitfalls
- Ingesting feeds without quality review; noisy feeds drown analysts and erode trust.
- Sharing without TLP discipline; one leak can end community membership.
- Treating MISP as an IOC dump; context is what makes intelligence actionable.
- Auto-blocking low-confidence IOCs; validate before enforcing.

## References
- OASIS STIX/TAXII specifications for structured sharing formats
- MISP project documentation
- NIST SP 800-150 Guide to Cyber Threat Information Sharing
- TLP 2.0 definitions from FIRST
- CISA AIS documentation for automated sharing concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
