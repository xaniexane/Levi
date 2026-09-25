---
skill_id: cyber_performing_osint_with_spiderfoot
name: OSINT with SpiderFoot
description: Automate open-source intelligence collection with SpiderFoot for domains, IPs, emails, and threat infrastructure pivoting.
risk: low
permissions: []
requires_confirmation: false
tags: [osint, spiderfoot, automation]
version: 1.0.0
---

## Purpose
- Automate the repetitive parts of OSINT so analysts spend time on analysis instead of manual lookups.
- Correlate findings across dozens of data sources automatically to surface linkages a human would miss.
- Standardize collection so every investigation of the same type covers the same sources.

## When to use
- When starting an investigation on a domain, IP, netblock, email, or username and needing broad initial coverage.
- When enriching incident IOCs with ownership, reputation, and infrastructure context.
- When running periodic exposure checks on the organization's own domains and executive identities.
- When triaging threat-intel feeds to decide which indicators deserve analyst attention.

## Prerequisites
- SpiderFoot installed on a dedicated host with API keys for the data sources you intend to use.
- A defined target and written authorization where the target belongs to a third party.
- Understanding of which modules are passive versus active so scans stay within policy.
- Storage and retention policy for collected data, since scans accumulate quickly.

## Procedure
1. Define the scan target and type: domain footprinting, IP investigation, email or username lookup.
2. Select modules appropriate to the engagement, starting with passive sources and adding active modules only with approval.
3. Configure API keys and rate limits so scans respect source terms of service.
4. Launch the scan with a descriptive name and record the target, module set, and start time in the case notes.
5. Let the scan complete, then review the correlation graph for clusters: shared infrastructure, registrant reuse, and name-server patterns.
6. Export key findings: interesting hosts, leaked credentials, exposed services, and reputation hits.
7. Validate high-value findings manually against the original source before including them in reports.
8. Tune the module set based on noise: disable sources that consistently return junk for your target types.
9. Archive scan results with the case and purge per the retention policy.
10. Schedule recurring scans for high-value targets such as corporate domains and executive names.
11. Feed validated entities into the threat-intel platform so future investigations start enriched.

## Expected outputs
- An automated collection report with correlated entities and source attribution.
- Validated findings ready for the investigation case file.
- A tuned module profile for the target type that the team can reuse.

## Pitfalls
- Running active modules against targets without authorization; some SpiderFoot modules touch the target directly.
- Treating automated results as verified; modules misparse data and sources go stale.
- Scanning without API keys and wondering why coverage is thin; most value comes from keyed sources.
- Letting scan data pile up without retention enforcement, creating a privacy liability.

## References
- SpiderFoot community module documentation for module selection
- SpiderFoot official documentation
- NIST SP 800-150 Guide to Cyber Threat Information Sharing
- SANS SEC487 OSINT methodology for validating automated findings
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
