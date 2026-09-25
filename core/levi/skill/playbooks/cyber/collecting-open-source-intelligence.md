---
skill_id: cyber_collecting_open_source_intelligence
name: Collecting Open Source Intelligence
description: Practitioner guide to planning, collecting, and validating OSINT for security investigations while respecting legal and ethical boundaries.
risk: info
permissions: []
requires_confirmation: false
tags: [osint, threat-intel, investigation]
version: 1.0.0
---
## Purpose
Open-source intelligence -- public records, social media, code repositories, certificate data, breach compilations -- enriches investigations and threat assessments. This playbook structures OSINT collection: defining requirements, choosing sources, validating findings, and documenting everything, while staying within legal and ethical limits.

## When to use
- Enriching incident investigations with external context on infrastructure or identities.
- Building threat-actor or campaign profiles.
- Conducting due diligence or executive-protection research.
- Monitoring public exposure of organizational assets and credentials.

## Prerequisites
- Defined intelligence requirements and scope boundaries.
- Legal review of what collection methods are permitted in your jurisdictions.
- Dedicated research environment (separate browser profile, VPN, or VM) for operational security.
- Source-evaluation criteria: reliability and credibility ratings.

## Procedure
1. Define the requirement. Write what you need to learn and why; scope prevents aimless browsing and over-collection.
2. Plan the sources. Match the requirement to source types: domain and certificate data, social platforms, code hosts, public records, breach datasets.
3. Protect the researcher. Use isolated browser profiles or VMs, avoid logging into personal accounts, and consider attribution risk before interacting with targets.
4. Collect systematically. Record URLs, timestamps, and screenshots for every finding; note exact queries used so the work is reproducible.
5. Evaluate sources. Rate each source's reliability and each claim's credibility; corroborate important claims with independent sources.
6. Analyze, don't just collect. Synthesize findings into assessments: what does this mean for the investigation or the threat picture.
7. Document and store. Write the OSINT report with citations; store raw collection securely with appropriate access controls.
8. Respect boundaries. Do not use deception to access non-public data, do not harass individuals, and escalate to legal when the line is unclear.

## Expected outputs
- OSINT collection plan tied to intelligence requirements.
- Validated findings with source citations and reliability ratings.
- Investigation or threat report incorporating the OSINT.

## Pitfalls
- Single-source OSINT presented as fact; corroboration is mandatory for important claims.
- Researcher attribution mistakes (logged-in accounts, direct contact) can compromise operations.
- Collecting personal data beyond the requirement creates privacy and legal risk.
- Screenshots without URLs and timestamps are weak evidence.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- OSINT framework concepts and public source directories
- Applicable privacy regulations for your jurisdictions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
