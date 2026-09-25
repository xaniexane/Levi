---
skill_id: cyber_building_threat_intelligence_platform
name: Building a Threat Intelligence Platform
description: Practitioner guide to standing up an internal threat-intelligence platform, from requirements and tooling to analyst workflows.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, operations, architecture]
version: 1.0.0
---
## Purpose
A threat-intelligence platform (TIP) is the system of record for what you know about adversaries: collection, analysis, storage, and dissemination. This playbook designs and deploys a TIP capability -- whether built on open-source tooling or commercial products -- sized to the organization's maturity, with workflows that serve the SOC, hunting, and leadership.

## When to use
- Formalizing threat intelligence beyond ad-hoc feeds and shared drives.
- Serving multiple consumers: SOC triage, threat hunting, incident response, executives.
- Consolidating collection, analysis, and dissemination in one system of record.
- Evaluating build-versus-buy for threat-intelligence tooling.

## Prerequisites
- Defined intelligence requirements: who needs what, in what format, how fast.
- Staffing: at least one analyst dedicated to intelligence production.
- Source inventory: feeds, sharing communities, OSINT, internal incident data.
- Integration targets: SIEM, ticketing, EDR, and reporting channels.

## Procedure
1. Write intelligence requirements. Interview SOC, IR, hunting, and leadership; document priority intelligence requirements (PIRs) that the platform must answer.
2. Choose the platform approach. Evaluate open-source (MISP, OpenCTI) versus commercial options against requirements, staffing, and budget.
3. Deploy the core. Install and secure the platform; configure authentication, roles, and data-retention policies.
4. Connect collection sources. Ingest feeds, sharing-community data, and internal incident artifacts; apply TLP and confidence handling.
5. Build analyst workflows. Define how raw data becomes finished intelligence: triage, analysis, review, and publication steps with quality checks.
6. Integrate consumers. Push indicators to controls, publish reports to stakeholders, and feed hunting hypotheses; measure delivery against the PIRs.
7. Establish sharing. Join relevant communities; define what you share outward and the approval process for external publication.
8. Measure and mature. Track requirement satisfaction, production volume, and consumer feedback; evolve the platform with the program's maturity.

## Expected outputs
- Operational TIP aligned to documented intelligence requirements.
- Analyst production workflow with quality controls.
- Consumer integrations and satisfaction measures.

## Pitfalls
- Buying a platform before defining requirements produces an expensive feed aggregator.
- No dedicated analyst time means the platform goes stale within months.
- Serving only the SOC ignores strategic consumers who fund the program.
- Publishing intelligence without review spreads errors with your name on them.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing
- OASIS STIX 2.1 specification
- MITRE ATT&CK for structuring adversary knowledge
- FIRST guidance on CSIRT intelligence functions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
