---
skill_id: cyber_performing_asset_criticality_scoring_for_vulns
name: Performing Asset Criticality Scoring for Vulnerabilities
description: Score asset criticality so vulnerability prioritization reflects business risk.
risk: info
permissions: []
requires_confirmation: false
tags: [vulnerability-management, asset-management, risk-assessment]
version: 1.0.0
---

## Purpose
This playbook builds an asset criticality scoring model that vulnerability management can consume: every asset gets a business-context score, and findings are prioritized by the combination of vulnerability severity and asset criticality — not CVSS alone.

## When to use
- Vulnerability backlogs are prioritized purely by CVSS, misallocating effort.
- Leadership asks "what is our actual risk?" and scanner counts do not answer it.
- Merging IT, OT, and cloud asset data into one risk view.

## Prerequisites
- Asset inventory with ownership, or a plan to build one as part of this work.
- Business input: which systems support revenue, safety, regulated data, or critical operations.
- Vulnerability data source(s) to join against the scored inventory.

## Procedure
1. **Define scoring dimensions.** Typical factors: data sensitivity, business function criticality, internet exposure, regulatory scope, and blast radius (what else fails if this fails).
2. **Set the scale and weights.** Use a simple, explainable scale (e.g., 1-5 per dimension, weighted sum); document why each weight was chosen so it survives scrutiny.
3. **Score with owners, not for them.** Have system and data owners validate criticality; security-assigned scores without business input get ignored.
4. **Join with vulnerability data.** Combine asset criticality with vulnerability severity and exploitability (KEV, public exploit) into a single prioritization score per finding.
5. **Operationalize in the workflow.** Feed the combined score into ticketing/SLA assignment so a medium on a critical asset outranks a high on a lab system automatically.
6. **Handle the unknowns.** Unscored or undiscovered assets default to a conservative criticality and generate a discovery task — never to "ignore."
7. **Review on change.** Re-score when business functions move, new regulated data appears, or architecture changes; review the model itself annually.

8. **Include cloud and OT assets.** Extend the model beyond traditional IT; a critical OT controller or cloud data store deserves the same scoring rigor.
9. **Validate with incidents.** After each significant incident, check whether the involved assets were scored correctly; real events are the best calibration data.

## Expected outputs
- Documented criticality model with dimensions, weights, and scoring guidance.
- Scored asset inventory joined to vulnerability findings.
- Prioritization logic embedded in the VM workflow with before/after comparisons.
- Example: a medium-severity CVE on the customer database (criticality 5/5) outranks a high-severity CVE on an isolated lab VM (criticality 1/5) in the remediation queue automatically.

## Pitfalls
- A 47-factor model nobody understands or maintains; simplicity beats precision.
- Scoring in a vacuum without asset owners, producing scores the business rejects.
- Letting unscored assets default to low criticality, hiding the riskiest unknowns.

## References
- NIST SP 800-30 Rev. 1, Guide for Conducting Risk Assessments.
- CIS Controls v8, Control 1 (Inventory and Control of Enterprise Assets).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
