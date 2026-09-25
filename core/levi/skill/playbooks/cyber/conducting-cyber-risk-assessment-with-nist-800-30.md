---
skill_id: cyber_conducting_cyber_risk_assessment_with_nist_800_30
name: Conducting Cyber Risk Assessments with NIST SP 800-30
description: Practitioner guide to performing structured cyber risk assessments following the NIST SP 800-30 methodology.
risk: info
permissions: []
requires_confirmation: false
tags: [governance, risk, assessment]
version: 1.0.0
---
## Purpose
NIST SP 800-30 provides a disciplined process for assessing information-system risk: identifying threats and vulnerabilities, determining likelihood and impact, and producing risk levels that drive treatment decisions. This playbook operationalizes that process so assessments are repeatable, defensible, and useful to decision-makers.

## When to use
- Performing a formal risk assessment for a system, project, or business unit.
- Supporting authorization decisions or risk-acceptance documentation.
- Prioritizing security investments with a defensible methodology.
- Meeting contractual or regulatory requirements for risk assessment.

## Prerequisites
- System characterization: boundaries, data types, users, and interconnections.
- Threat and vulnerability inputs: threat intel, scan results, audit findings, pentest reports.
- Defined risk scales (likelihood and impact levels) agreed with stakeholders.
- Access to system owners and operators for interviews.

## Procedure
1. Prepare and characterize. Document the system boundary, data classification, and criticality; agree on the assessment scope and risk scales.
2. Identify threat sources and events. List relevant threat sources (adversarial, accidental, environmental) and the events they could cause against this system.
3. Identify vulnerabilities and predisposing conditions. Gather scan results, configuration reviews, and architectural weaknesses; note missing controls.
4. Determine likelihood. Assess the probability that each threat-vulnerability pair leads to compromise, using historical data and threat intelligence.
5. Determine impact. Assess confidentiality, integrity, and availability impacts in business terms, including regulatory and reputational consequences.
6. Determine risk levels. Combine likelihood and impact per the defined matrix; document the rationale for each rating.
7. Recommend risk responses. For each significant risk, propose mitigation, transfer, acceptance, or avoidance with owners and timelines.
8. Document and communicate. Produce the risk assessment report, brief stakeholders, and feed results into the risk register and treatment plans.

## Expected outputs
- Risk assessment report with threat-vulnerability pairs, ratings, and rationale.
- Prioritized risk treatment recommendations with owners.
- Updated risk register entries.

## Pitfalls
- Generic threat lists without system-specific relevance produce generic results.
- Likelihood guesses without data; ground them in intel and history.
- Impact stated only technically; translate to business consequences.
- Assessments filed and forgotten; integrate with ongoing risk management.

## References
- NIST SP 800-30 Rev. 1, Guide for Conducting Risk Assessments
- NIST SP 800-37 Rev. 2, Risk Management Framework
- NIST SP 800-39, Managing Information Security Risk
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
