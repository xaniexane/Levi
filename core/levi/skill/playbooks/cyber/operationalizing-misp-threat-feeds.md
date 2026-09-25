---
skill_id: cyber_operationalizing_misp_threat_feeds
name: Operationalizing MISP Threat Feeds
description: Turn MISP threat intelligence into automated detection and response actions.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intelligence, misp, automation]
version: 1.0.0
---
## Purpose
This playbook makes MISP operational: syncing the right feeds, curating events, and pushing high-confidence indicators into detection and enforcement tools automatically — while keeping analysts in control of what gets blocked.

## When to use
- MISP is installed but feeds sit unread and never reach controls.
- Analysts manually copy IOCs from MISP into firewall rules.
- You need measurable value from threat-intel investment.

## Prerequisites
- MISP instance with admin access, feed configuration, and sync users for sharing communities.
- Defined confidence and TLP handling policy.
- API access from MISP to downstream tools (SIEM, EDR, firewall, DNS).

## Procedure
1. **Select feeds deliberately.** Enable feeds matching your sector and threat model; disable low-precision or duplicative feeds after a trial period.
2. **Tune the sync and filters.** Use feed filters (tags, TLP, event age) so only relevant, shareable content lands in your instance; respect distribution settings.
3. **Curate locally.** Analysts tag events with confidence, add internal sightings, and expire stale indicators; automation should amplify analyst judgment, not replace it.
4. **Build the export pipeline.** Use MISP's export/API to push indicators by type: hashes to EDR blocklists, IPs/domains to firewall/DNS, URLs to email gateway — tagged by source feed.
5. **Gate automatic blocking.** Auto-block only high-confidence indicators from trusted feeds with recent sightings; route everything else to detection-only or analyst review.
6. **Close the loop.** When an exported indicator fires in your environment, record the sighting back in MISP; use hit rates to prune feeds and tune confidence.
7. **Share back.** Publish your own sanitized events to your sharing communities; a one-way consumer eventually loses access to quality sharing.

8. **Sync with partners deliberately.** Configure push/pull sync with sharing communities per their TLP rules; verify what you publish is sanitized of internal hostnames and victim identities.
9. **Audit the automation.** Quarterly, review what the pipeline blocked automatically and confirm every auto-block was correct; automation without audit becomes unaccountable.

## Expected outputs
- Curated MISP instance with documented feed selection and filter policy.
- Automated indicator pipeline to enforcement points with blocking gates.
- Metrics: indicator hit rate per feed, time from publish to enforcement, sightings recorded.
- Example: a MISP event for an active phishing campaign auto-pushes 12 domains to DNS blocking and the email gateway within 10 minutes, while lower-confidence indicators go to SIEM detection-only rules for analyst review.

## Pitfalls
- Auto-blocking every feed indicator: expect self-inflicted outages from false positives.
- Ignoring TLP and distribution settings when re-sharing.
- Never expiring indicators: stale blocks accumulate and erode trust in the pipeline.

- Enabling dozens of feeds at once and overwhelming analysts; add feeds one at a time with a 30-day precision trial.
- Exporting indicators without the MISP event context; a bare IP without its campaign context is far less actionable.

## References
- MISP documentation (misp-project.org/documentation).
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- MISP best-practice guides (misp-project.org/best-practices) — feed and sharing hygiene.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
