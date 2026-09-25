---
skill_id: cyber_conducting_gdpr_compliance_assessment
name: Conducting GDPR Compliance Assessments
description: Practitioner guide to assessing organizational compliance with the EU General Data Protection Regulation across data, processes, and controls.
risk: info
permissions: []
requires_confirmation: false
tags: [governance, compliance, privacy]
version: 1.0.0
---
## Purpose
GDPR compliance spans legal, technical, and organizational measures, and enforcement penalties are significant. This playbook structures a compliance assessment: mapping personal-data processing, evaluating lawful bases and rights fulfillment, reviewing technical controls, and producing a gap analysis with a remediation roadmap. It is an assessment methodology, not legal advice.

## When to use
- Performing a periodic GDPR compliance review.
- Preparing for a supervisory-authority inquiry or audit.
- Assessing a new product or processing activity (supporting a DPIA).
- After organizational changes (mergers, new markets, new systems) that affect data processing.

## Prerequisites
- Records of processing activities (Article 30 records) or the raw material to build them.
- Data-flow diagrams for key systems handling personal data.
- Access to DPO, legal, IT, and business process owners.
- Understanding that the assessment team advises; legal counsel determines legal positions.

## Procedure
1. Scope the assessment. Define which processing activities, systems, and business units are in scope; prioritize high-risk processing.
2. Map data flows. Document what personal data is collected, where it flows, where it is stored, retention periods, and third-party sharing.
3. Review lawful bases and notices. Verify each processing purpose has a documented lawful basis and that privacy notices match actual practice.
4. Assess data-subject rights. Test the processes for access, rectification, erasure, portability, and objection requests against the one-month timeline.
5. Evaluate technical and organizational measures. Review encryption, access controls, logging, breach-detection capability, and the 72-hour breach-notification process.
6. Check vendor management. Verify data-processing agreements with processors and transfer mechanisms for non-EEA transfers.
7. Assess DPIAs and records. Confirm data-protection impact assessments exist where required and that Article 30 records are complete and current.
8. Report gaps and roadmap. Produce findings ranked by regulatory risk with remediation owners and timelines; track to closure.

## Expected outputs
- GDPR gap analysis with findings ranked by risk.
- Remediation roadmap with owners and timelines.
- Updated records of processing and DPIA status.

## Pitfalls
- Treating the assessment as a checkbox exercise; regulators look for effectiveness.
- Missing shadow processing (marketing tools, spreadsheets) that never made the records.
- Technical measures documented but not actually implemented or tested.
- No legal review of conclusions that state compliance positions.

## References
- EU General Data Protection Regulation (Regulation 2016/679) text
- EDPB guidelines on key GDPR concepts
- ISO/IEC 27701, Privacy information management
- NIST Privacy Framework (for control mapping context)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
