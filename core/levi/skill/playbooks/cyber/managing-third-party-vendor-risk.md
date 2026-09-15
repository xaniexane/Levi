---
skill_id: cyber_managing_third_party_vendor_risk
name: Managing Third-Party Vendor Risk
description: Run a third-party risk management program from onboarding to continuous monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [third-party-risk, grc, vendor-management]
version: 1.0.0
---
## Purpose
This playbook establishes third-party risk management: tiering vendors by risk, assessing them before and during the relationship, contracting for security, and monitoring continuously — so a vendor compromise does not become your breach.

## When to use
- Vendors hold your data or connect to your network without consistent assessment.
- Procurement signs contracts faster than security can review them.
- Regulators or customers ask for evidence of vendor oversight.

## Prerequisites
- A vendor inventory with data-access and connectivity details per vendor.
- Standard assessment artifacts: SIG questionnaire (or equivalent), SOC 2 reports, penetration test summaries.
- Procurement partnership: security review must be a gate, not an afterthought.

## Procedure
1. **Inventory and tier vendors.** Classify by data sensitivity handled, network access, and business criticality; critical vendors get deep assessment, low-risk vendors get a lightweight track.
2. **Assess before contracting.** Review security documentation, run a questionnaire for critical vendors, and check for known breaches or poor security posture signals.
3. **Contract for security.** Require breach notification timelines, right-to-audit, data handling and deletion terms, subcontractor disclosure, and SLA-backed security commitments.
4. **Verify, do not just collect.** For critical vendors, validate claims: review the actual SOC 2 (not just the letter), check certificate validity periods, and confirm remediation of past findings.
5. **Monitor continuously.** Track security rating changes, breach disclosures, certificate expirations, and fourth-party dependencies; re-assess critical vendors annually.
6. **Plan for vendor failure.** Document exit strategies: data return/deletion, credential revocation, and service continuity for critical vendors.
7. **Report to leadership.** Maintain a vendor risk register with residual risk ratings and present it to the risk committee on a defined cadence.

8. **Assess fourth parties.** Ask critical vendors about their own key sub-processors; your data often flows further than the contract suggests.
9. **Tie to procurement gates.** No purchase order for a critical vendor without a completed risk assessment; embed the gate in the procurement system, not in policy documents.

## Expected outputs
- Tiered vendor inventory with risk ratings and assessment status.
- Contract security clauses standardized in procurement templates.
- Continuous monitoring alerts and annual re-assessment records.
- Example: a critical SaaS vendor's expired SOC 2 triggers an automatic review task; the assessment finds unremediated prior-year exceptions, and renewal is held until a remediation plan is committed.

## Pitfalls
- One-time onboarding assessments that never get revisited.
- Accepting a SOC 2 report at face value without reading scope and exceptions.
- No exit plan: discovering at breach time that you cannot revoke or extract your data.

- Assessing the vendor's security once while their infrastructure changes monthly; continuous monitoring must be genuinely continuous, not annual.
- Treating a vendor's marketing security page as evidence; require attestations, reports, or contractual commitments, not claims.

## References
- NIST SP 800-161 Rev. 1, Cybersecurity Supply Chain Risk Management Practices.
- SIG questionnaire resources (sharedassessments.org).
- ISO/IEC 27036 (supplier relationships) — information security for supplier relationships.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
