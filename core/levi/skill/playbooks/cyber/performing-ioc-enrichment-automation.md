---
skill_id: cyber_performing_ioc_enrichment_automation
name: IOC Enrichment Automation
description: Automate indicator enrichment with reputation and context lookups.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, automation, ioc]
version: 1.0.0
---
# IOC Enrichment Automation

## Purpose

Raw indicators without context are just strings. Enrichment — reputation
scores, geolocation, passive DNS, WHOIS, sandbox verdicts — turns them
into decisions. This playbook designs an automated enrichment pipeline
that attaches consistent, sourced context to every indicator the SOC
handles.

## When to use

- Reducing analyst time spent on manual lookups during triage.
- Standardizing the context attached to alerts and cases.
- Feeding enriched indicators into scoring and prioritization.
- Preparing intel for automated blocking decisions.

## Prerequisites

- API access to enrichment sources (threat-intel platforms, passive
  DNS, WHOIS, sandbox verdicts) with rate limits understood.
- A SOAR platform, TIP, or scripted pipeline where enrichment logic
  lives in version control.
- Data-handling rules: what may be sent to external APIs (hashes
  usually fine; internal URLs or file contents usually not).

## Procedure

1. Define the enrichment schema: per indicator type, which fields to
   collect (IP: ASN, geolocation, reputation; domain: registrar age,
   passive DNS; hash: sandbox verdicts, first seen).
2. Build the pipeline in stages: normalize input, query sources in
   parallel with timeouts, and merge results into a single enriched
   record with per-source timestamps.
3. Cache aggressively: store results with TTLs so repeated lookups of
   the same indicator do not burn API quota or slow triage.
4. Handle failures gracefully: a dead source should degrade the record
   (marked "source unavailable"), not fail the whole pipeline or block
   triage.
5. Score consistently: combine source verdicts into a single risk score
   with transparent weighting, and record which sources contributed.
6. Respect privacy and TLP: never send internal hostnames, file
   contents, or TLP:RED material to public enrichment APIs.
7. Log everything: source queries, responses, and scores become the
   audit trail when an automated block is later questioned.
8. Review source value quarterly: drop sources with poor accuracy or
   uptime, and recalibrate weights as source quality changes.

## Expected outputs

- An automated pipeline producing enriched indicator records on
  demand.
- A documented schema, scoring model, and source list with TTLs.
- Audit logs of enrichment decisions.
- Quarterly source-quality reviews.

## Pitfalls

- Sending sensitive data to public APIs: define the boundary before
   building.
- Single-source scoring: one vendor's verdict is an opinion, not a
   decision.
- No caching: quota exhaustion during an incident is a self-inflicted
   outage.
- Treating enrichment as verdict: context informs the analyst, it does
   not replace judgment on ambiguous indicators.

## References

- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- MISP documentation on enrichment modules
- FIRST Traffic Light Protocol (TLP) definitions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
