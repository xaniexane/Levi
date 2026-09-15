---
skill_id: cyber_implementing_security_information_sharing_with_stix2
name: Implementing Security Information Sharing with STIX 2
description: Share cyber threat intelligence using STIX 2.1 over TAXII: modeling, producing, consuming, and operationalizing shared intelligence.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, stix, sharing]
version: 1.0.0
---
## Purpose

STIX 2.1 (over TAXII 2.1) is the standard language for machine-readable
threat-intel sharing. This playbook covers implementing a STIX 2-based
sharing capability: modeling your intelligence as STIX objects,
producing and consuming via TAXII, and turning shared intel into
operational defenses.

## When to use

- Joining an ISAC/ISAO or community sharing group.
- Automating intel ingestion from commercial or government feeds.
- Publishing your own finished intelligence for peers.
- Standardizing internal intel representation across tools.

## Prerequisites

- A threat-intel platform (TIP) with STIX 2.1/TAXII 2.1 support, or
  libraries for building one.
- Defined sharing policy: what may be shared, with whom, under which
  TLP markings.
- Collection requirements so consumed intel maps to defense needs.
- Deduplication and confidence-grading processes.

## Procedure

1. **Model with STIX domain objects.** Represent intelligence using
   STIX 2.1 objects: Identity, Threat Actor, Intrusion Set, Campaign,
   Malware, Tool, Vulnerability, Indicator, Observed Data, Attack
   Pattern (ATT&CK-mapped), and Report — linked with Relationship
   objects. Consistent modeling makes intel consumable.
2. **Produce indicators correctly.** Indicators need: valid STIX
   patterns, labels, confidence, valid-from/valid-until timestamps,
   and TLP markings. Expired or unmarked indicators are the top
   quality failure in shared intel — enforce at production time.
3. **Stand up TAXII collections.** Organize sharing into TAXII 2.1
   collections by topic or sensitivity (e.g. ransomware IOCs,
   sector-specific campaigns). Control access per collection and
   document what each contains.
4. **Consume and normalize feeds.** Ingest external STIX feeds into
   the TIP; normalize scoring, deduplicate against existing holdings,
   and tag by source reliability. Do not auto-block on unvetted
   external indicators — validate first.
5. **Operationalize consumed intel.** Map indicators to enforcement:
   EDR, firewall/proxy, email gateway, and SIEM detections. Track
   which sources produce actionable intel and prune feeds with
   sustained low value.
6. **Share your own reporting.** Convert finished internal analysis
   into STIX Reports with supporting objects; apply TLP correctly;
   sanitize victim and source identities before release. Sharing
   improves the community's defense — including yours, reciprocally.
7. **Measure sharing value.** Track: consumed indicators that fired
   (true positives), time from external publication to internal
   enforcement, and community feedback on your shared intel. Use
   these to tune sources and production quality.
8. **Govern the program.** Maintain sharing agreements, review TLP
   compliance, audit what was shared, and train producers on
   markings and sanitization.

## Expected outputs

- STIX 2.1 modeling standards and production templates.
- TAXII collections with access controls and documentation.
- Normalized, deduplicated intel holdings with source scoring.
- Enforcement mappings with effectiveness metrics.
- Sharing agreements and compliance audit records.

## Pitfalls

- Sharing without TLP markings or with wrong markings — the
   fastest way to lose sharing partners' trust.
- Auto-blocking unvetted external indicators — false positives
   cause outages; validate before enforcing.
- Indicators without expiry — stale intel accumulates into
   operational drag; enforce valid-until.
- One-way consumption without contributing — sharing communities
   are reciprocal; contribute to sustain access.
- Inconsistent identity objects breaking correlation — standardize
   producer identities across your STIX output.

## References

- STIX 2.1 and TAXII 2.1 specifications (OASIS Cyber Threat
  Intelligence TC)
- NIST SP 800-150: Guide to Cyber Threat Information Sharing
- FIRST: TLP 2.0 markings
- ISAC/ISAO sharing guidance for your sector
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
