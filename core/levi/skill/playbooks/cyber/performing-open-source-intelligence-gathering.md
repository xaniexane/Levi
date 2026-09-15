---
skill_id: cyber_performing_open_source_intelligence_gathering
name: Open Source Intelligence Gathering
description: Collect and analyze publicly available information to support investigations, threat assessments, and due diligence.
risk: info
permissions: []
requires_confirmation: false
tags: [osint, investigation, intelligence]
version: 1.0.0
---

## Purpose
- Build a complete picture of a subject, domain, or threat actor using only lawful public sources.
- Support incident response with external context: who owns attacking infrastructure, what is exposed, what is being said.
- Establish a defensible OSINT tradecraft standard so findings are accurate, sourced, and legally sound.

## When to use
- When investigating phishing domains, suspicious infrastructure, or social-engineering lures.
- When assessing what an attacker can learn about the organization from public sources.
- When vetting vendors, partners, or acquisition targets for security-relevant public exposure.
- When enriching threat-intel reports with actor history and infrastructure linkages.

## Prerequisites
- A defined intelligence requirement: what question the collection must answer and what is out of scope.
- Dedicated research accounts and tooling separated from personal identities, with OPSEC appropriate to the sensitivity.
- Legal and policy review confirming the collection methods are authorized in the relevant jurisdictions.
- A system for recording sources, timestamps, and confidence levels for every collected item.

## Procedure
1. Write the collection plan: priority intelligence requirements, sources to check, and explicit out-of-scope boundaries.
2. Start with domain and infrastructure sources: WHOIS history, DNS records, certificate transparency logs, and passive DNS.
3. Pivot through infrastructure linkages: shared IPs, name servers, registrant patterns, and hosting providers.
4. Review public code, documents, and paste sites for leaked credentials, keys, or internal details tied to the subject.
5. Check social and professional profiles for role, technology, and relationship information relevant to the requirement.
6. Correlate findings across sources, resolving conflicts and noting which claims rest on single sources.
7. Assess confidence for each key judgment and record the sourcing chain so findings can be re-verified.
8. Sanitize the report for the intended audience, removing collection methods that should stay internal.
9. Archive raw collection with timestamps in case findings are challenged later.
10. Brief stakeholders on both findings and limitations, including what public sources could not confirm.
11. Check breach-combination and credential-dump sources for organizational email patterns using legitimate feeds.
12. Produce a sanitized tear-line version of the report for wider distribution.

## Expected outputs
- An OSINT report answering the intelligence requirement with sourced, confidence-rated findings.
- An infrastructure map linking domains, IPs, certificates, and accounts where relevant.
- A collection log that makes every finding traceable to its source and time.

## Pitfalls
- Collecting beyond the authorized scope, especially into accounts or systems that require authentication under false pretenses.
- Presenting single-source claims as confirmed; OSINT is full of lookalikes, stale data, and deliberate deception.
- Burning research identities through poor OPSEC, which alerts the subject and taints future collection.
- Downloading or retaining stolen data beyond what the investigation requires.

## References
- NIST SP 800-30 Guide for Conducting Risk Assessments for risk framing
- NIST SP 800-150 Guide to Cyber Threat Information Sharing
- SANS SEC487 OSINT course materials and methodology
- Bellingcat online investigation toolkit guidance for verification techniques
- Applicable privacy laws and organizational acceptable-use policies
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
