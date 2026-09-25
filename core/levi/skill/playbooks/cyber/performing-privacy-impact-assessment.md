---
skill_id: cyber_performing_privacy_impact_assessment
name: Privacy Impact Assessment
description: Conduct privacy impact assessments for new systems and data processing to identify and mitigate privacy risks.
risk: info
permissions: []
requires_confirmation: false
tags: [privacy, governance, assessment]
version: 1.0.0
---

## Purpose
- Identify privacy risks in new projects before personal data starts flowing.
- Demonstrate accountability to regulators, customers, and partners with documented assessments.
- Embed privacy-by-design into project lifecycles instead of bolting it on after launch.

## When to use
- When launching a new product, feature, or system that processes personal data.
- When changing data flows: new vendors, new analytics, new international transfers.
- When regulations require it, such as high-risk processing under GDPR or similar laws.
- After privacy incidents, to reassess the processing that failed.

## Prerequisites
- A PIA template aligned with applicable regulations and organizational policy.
- Stakeholder access: product, engineering, legal, and data protection officer involvement.
- Data flow diagrams or the ability to build them with the project team.
- Knowledge of the relevant legal bases, retention rules, and individual rights.

## Procedure
1. Describe the processing: what personal data, from whom, for what purposes, and on what legal basis.
2. Map data flows end to end: collection, storage, sharing, international transfers, and deletion.
3. Identify privacy risks: excessive collection, weak security, opaque purposes, and rights fulfillment gaps.
4. Assess necessity and proportionality: is each data element truly needed for the stated purpose.
5. Evaluate security controls protecting the data: encryption, access controls, logging, and breach detection.
6. Check individual rights handling: access, correction, deletion, portability, and objection workflows.
7. Review vendor and sub-processor arrangements, contracts, and transfer mechanisms.
8. Consult stakeholders and, where required, the data protection officer or supervisory authority.
9. Document mitigations with owners and deadlines, and record residual risks with acceptance decisions.
10. Set a review trigger: reassess when the processing changes materially or on a defined schedule.

## Expected outputs
- A completed PIA with risks, mitigations, owners, and residual risk decisions.
- Updated data flow documentation and records of processing.
- Review triggers tied to project milestones.
- An updated record of processing activities reflecting the assessed changes.
- A communication plan for notifying individuals where the assessment identifies new risks.

## Pitfalls
- Treating the PIA as a checkbox after launch; its value is in shaping design before build.
- Describing intended flows instead of actual ones; verify with engineering, not just product specs.
- Ignoring vendors and sub-processors, where many privacy failures actually occur.

## References
- IAPP PIA practice guidance
- NIST Privacy Framework
- GDPR Article 35 guidance on data protection impact assessments
- ISO/IEC 27701 privacy information management guidance
- Applicable national privacy laws for the operating jurisdictions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
