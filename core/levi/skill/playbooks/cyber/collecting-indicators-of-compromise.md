---
skill_id: cyber_collecting_indicators_of_compromise
name: Collecting Indicators of Compromise
description: Practitioner guide to systematically extracting, validating, and packaging indicators of compromise from investigations.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, incident-response, forensics]
version: 1.0.0
---
## Purpose
Indicators of compromise are the concrete artifacts of an intrusion: hashes, domains, IPs, URLs, email addresses, registry keys, mutexes. This playbook standardizes how analysts collect them during investigations -- from which sources, with what context, and in what format -- so IOCs are accurate, actionable, and safe to share.

## When to use
- During active incident response to build the indicator set for hunting and blocking.
- After malware analysis to extract network and host indicators.
- Preparing intelligence products for internal teams or sharing communities.
- Auditing whether past incidents produced usable indicators.

## Prerequisites
- Access to investigation artifacts: memory images, disk images, logs, sandbox reports.
- Standard IOC format agreed by the team (STIX, OpenIOC, CSV, or MISP events).
- Validation sources: sandboxes, reputation services, passive DNS.
- TLP and handling policy for any external sharing.

## Procedure
1. Identify collection sources. List where indicators live for this case: malware samples, C2 traffic, phishing emails, persistence mechanisms, lateral-movement logs.
2. Extract host indicators. Pull file hashes, paths, registry keys, scheduled tasks, services, mutexes, and named pipes from forensic artifacts.
3. Extract network indicators. Pull domains, URLs, IPs, ports, TLS certificates, JA3 hashes, and email addresses from traffic and logs.
4. Validate each indicator. Confirm maliciousness via sandbox detonation, reputation checks, and correlation with known-bad infrastructure; discard benign overlaps.
5. Add context. Record first seen, last seen, confidence, related malware or actor, and the source artifact for every indicator.
6. Deduplicate. Merge with existing indicator sets; update sightings rather than creating duplicates.
7. Package for consumers. Format for the destination: SIEM lookups for hunting, firewall lists for blocking, STIX/MISP for sharing.
8. Age and retire. Set review dates; retire indicators that go quiet, get sinkholed, or are re-registered by legitimate owners.

## Expected outputs
- Validated IOC package with context and confidence ratings.
- Indicators loaded into hunting and blocking controls.
- Sharing-ready package with TLP markings where applicable.

## Pitfalls
- Unvalidated indicators cause false-positive blocks and erode trust.
- Collecting without context (no dates, no confidence) makes IOCs unusable later.
- Duplicate indicators across cases inflate counts and confuse analysts.
- Dynamic infrastructure (fast-flux, cloud IPs) ages out in hours; note volatility.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- OASIS STIX 2.1 specification
- FIRST Traffic Light Protocol (TLP) version 2.0
- MITRE ATT&CK for mapping indicators to techniques
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
