---
skill_id: cyber_performing_indicator_lifecycle_management
name: Indicator Lifecycle Management
description: Manage threat indicators from ingestion through expiry with quality control.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, ioc, process]
version: 1.0.0
---
# Indicator Lifecycle Management

## Purpose

Indicators rot: IPs get reassigned, domains change hands, hashes get
reused by unrelated software. A feed without lifecycle management becomes
a false-positive machine. This playbook runs indicators through a full
lifecycle — ingestion, validation, enrichment, deployment, review, and
expiry — so the intel you act on stays trustworthy.

## When to use

- Standing up or maturing a threat-intelligence function.
- Reducing false positives from stale blocking lists.
- Preparing intel for sharing with partners or ISACs.
- Auditing whether deployed indicators are still valid.

## Prerequisites

- A TIP or tracking system (MISP, OpenCTI, or a structured store) that
  records per-indicator metadata: source, confidence, first/last seen,
  and expiry.
- Defined confidence and handling markings (TLP) applied consistently.
- Consumption points inventoried: firewall, proxy, EDR, SIEM — so you
  know where each indicator is enforced.

## Procedure

1. Ingest with metadata: every indicator enters with source,
   collection date, TLP marking, and initial confidence — never as a
   bare value.
2. Validate before deployment: check the indicator against allowlists
   (CDNs, shared hosting, your own infrastructure) and confirm it is
   not already widely benign; reject or downgrade on collision.
3. Enrich systematically: resolve IPs to ASNs and hosting providers,
   check domain registration age, and link to known campaigns or
   malware families.
4. Deploy by confidence tier: high-confidence indicators go to blocking,
   medium to alerting, low to hunting only — never block on a single
   low-confidence source.
5. Set expiry at ingestion: short-lived for IPs (days to weeks),
   longer for hashes and domains, with automatic review triggers.
6. Review on schedule: re-validate deployed indicators against current
   data; expire or downgrade anything that no longer holds.
7. Measure quality: track false-positive rate per source and per type,
   and feed the scores back into source trust decisions.
8. Share responsibly: export validated, TLP-compliant indicators to
   partners with full context, not bare lists.

## Expected outputs

- A documented lifecycle with stages, owners, and SLAs.
- Per-indicator metadata: source, confidence, TLP, expiry.
- Quality metrics per feed: false-positive rate, time-to-expire.
- Sharing packages with context for partners.

## Pitfalls

- Deploying feeds directly to blocking without validation: one bad
   feed can block a CDN and take down business apps.
- Never expiring indicators: the list only grows, and so does the
   noise.
- Ignoring TLP: sharing a TLP:RED indicator burns sources and trust.
- Measuring volume instead of quality: 10,000 stale indicators are
   worse than 100 fresh ones.

## References

- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- MISP documentation on taxonomies and sharing models
- FIRST Traffic Light Protocol (TLP) definitions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
