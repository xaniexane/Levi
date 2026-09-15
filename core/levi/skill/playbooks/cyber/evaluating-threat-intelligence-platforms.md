---
skill_id: cyber_evaluating_threat_intelligence_platforms
name: Evaluating Threat Intelligence Platforms
description: Evaluate and select a threat intelligence platform (TIP) against operational criteria.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, procurement, evaluation]
version: 1.0.0
---
## Purpose

Threat intelligence platforms promise to operationalize intel — aggregation, enrichment, dissemination — but products differ enormously in data quality, integrations, and analyst workflow fit. This playbook provides a structured evaluation methodology: defining requirements from your use cases, testing with your data, and selecting on operational value rather than feature checklists.

## When to use

- You need to select a TIP (first purchase or replacement).
- Leadership wants justification for threat-intel spending.
- Comparing open-source vs. commercial TIP options.
- Current TIP isn't delivering value and you need an assessment framework.

## Prerequisites

- Documented threat-intel use cases: detection enrichment, hunting, incident response, vulnerability prioritization.
- Sample data: your historical IOCs, past incident indicators, and current feed subscriptions for testing.
- Integration inventory: SIEM, SOAR, EDR, firewall/proxy — what the TIP must feed.
- Evaluation team: intel analysts, detection engineers, SOC leads, and procurement.

## Procedure

1. Define requirements from use cases, not features. For each use case specify measurable needs: detection enrichment (lookup latency, API rate limits, STIX/TAXII support), hunting (graph/pivot capabilities, historical depth), incident response (bulk IOC export, confidence scoring), and sharing (TAXII server, trust-group support). Requirements without use cases become feature bingo — vendors always win feature bingo.
2. Test with your data, not vendor data. Provide each candidate: a set of your historical IOCs (measure match rates and enrichment depth), a past incident's indicator set (measure pivot/investigation support), and your current feeds (measure dedup and correlation value). Score on analyst time saved and detection improvement — not dashboard aesthetics.
3. Evaluate data quality ruthlessly. Measure: false-positive rate on a labeled set, timeliness (how fast new threats appear vs. your other sources), context depth (is it an IP, or an IP with campaign, TTP, and confidence?), and decay handling (does old intel expire or linger?). A TIP full of stale, context-free IOCs is a liability, not an asset.
4. Assess operational fit. Test: SIEM/SOAR/EDR integrations (bidirectional? or export-only?), analyst workflow (can an analyst go from alert to intel to action without swearing?), access controls and audit logging, API completeness for automation, and total cost including feeds, implementation, and analyst training. Run a 30-day pilot with real SOC workflows before deciding.
5. Compare build vs. buy vs. open source honestly. Open-source options (MISP and similar) offer strong capabilities with integration effort; commercial platforms offer support and curated data at cost. Model 3-year TCO including staffing — an under-staffed commercial TIP delivers less than a well-run open-source one.
6. Decide with a scored matrix and document it. Weight criteria by your use cases, score each candidate from pilot evidence, document the decision rationale, and define success metrics for post-implementation review (6 months): intel-driven detections added, mean time to enrich, analyst satisfaction. Revisit if metrics miss.

## Expected outputs

- Use-case-derived requirements with measurable acceptance criteria.
- Pilot scorecards: your data tested against each candidate.
- 3-year TCO model: licenses, feeds, implementation, staffing.
- Decision record with success metrics and review date.

## Pitfalls

- Evaluating on vendor-provided data guarantees misleading results — always test with your own.
- Feature checklists favor incumbents; weight by your actual use cases.
- Underestimating integration and tuning effort is the top cause of TIP shelfware.
- More feeds don't equal more intelligence — measure signal, not volume.
- Skipping the pilot means discovering workflow mismatches after purchase.

## References

- NIST SP 800-150 (cyber threat information sharing); MITRE guidance on threat-intel program maturity; Gartner/Forrester TIP evaluations (for market context, not as sole source)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
