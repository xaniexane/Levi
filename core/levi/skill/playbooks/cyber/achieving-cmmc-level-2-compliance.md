---
skill_id: cyber_achieving_cmmc_level_2_compliance
name: Achieving CMMC Level 2 Compliance
description: Roadmap for CMMC Level 2: 110 practices across 14 domains, scoping, POA&M, and assessment readiness.
risk: info
permissions: []
requires_confirmation: false
tags: [compliance]
version: 1.0.0
---
# Achieving CMMC Level 2 Compliance

## Purpose

Provide a structured, auditable path for a defense-industrial-base
organization to reach CMMC Level 2 (110 practices aligned to NIST SP 800-171
Rev 2), pass a C3PAO assessment, and maintain continuous compliance.
Covers scoping, gap remediation, evidence packaging, the assessment itself,
and sustainment.

## When to use

- Your organization handles CUI or FCI under DoD contracts and a
  solicitation requires CMMC Level 2.
- Leadership has set a target assessment date and you need a work breakdown
  from current state to "assessment-ready."
- You inherited a partial NIST 800-171 program and need to close the gap to
  the full 110 practices.
- Post-assessment: remediating POA&M items and preparing for the three-year
  reassessment cycle.
- Annual affirmation season: refreshing evidence that controls are still
  operating effectively.

## Prerequisites

- Written authorization from executive leadership defining the CMMC
  assessment scope (which enclaves, systems, people, and facilities process
  CUI) and funding the remediation program.
- Chain-of-custody notes: evidence artifacts (configs, logs, screenshots)
  must be timestamped, versioned, and attributable to a collector for
  assessor review.
- A designated compliance lead plus stakeholders from IT, security, HR,
  legal, and facilities — with named alternates so the program survives
  turnover.
- Current System Security Plan (SSP) draft or equivalent system inventory;
  if none exists, building it is step one.
- Access to the current CMMC model documentation and assessment guides —
  verify you are working from the current rulemaking, not outdated drafts.

## Procedure

1. **Define and freeze the assessment scope.** Identify every asset that processes, stores, or transmits CUI. CMMC scoping guidance distinguishes in-scope asset categories: CUI assets, security-protection assets, contractor risk-managed assets, and specialized assets. Document the boundary in a network diagram, asset inventory, and data-flow description. Assessors test the boundary first — get it right before spending on controls.
2. **Consider enclave strategy deliberately.** Many organizations reduce scope (and cost) by isolating CUI into a dedicated enclave rather than bringing the entire enterprise into scope. Model both options: enclave build-out cost vs. enterprise-wide control implementation. Document the decision and its rationale for assessors.
3. **Map current state to the 110 practices.** Build a traceability matrix: one row per NIST SP 800-171 Rev 2 requirement (14 families — Access Control, Awareness & Training, Audit & Accountability, etc.), with columns for implementation status, evidence location, and owner. Mark each Met / Not Met / Inherited / Not Applicable (N/A is rarely accepted — justify heavily and expect pushback).
4. **Produce or update the SSP.** For every practice, write *how* it is implemented in your environment (not just that it is). The SSP is the primary artifact the assessment team reads; vague SSP language ("we use industry best practices") is the most common source of findings. Name tools, configurations, and responsible roles per practice.
5. **Close gaps with a POA&M.** For each Not Met practice, create a Plan of Action & Milestones entry with remediation tasks, owners, and dates. Note: at Level 2 a limited set of practices may remain open under POA&M at assessment time, but assessors expect closure within 180 days, and some practices are never POA&M-eligible — verify current CMMC guidance before relying on this.
6. **Implement the heavy-lift controls first.** In practice these dominate timelines: FIPS-validated encryption for CUI at rest and in transit (3.13.11), multifactor authentication (3.5.3), audit logging with centralized review and alerting (3.3.x), incident-response capability with testing (3.6.x), and media protection (3.8.x). Start procurement and engineering here — these have the longest lead times.
7. **Operationalize evidence collection.** Assessors use three methods — Examine, Interview, Test. For each practice, pre-stage: (a) documents to examine (policies, configurations, logs); (b) personnel available to interview (named roles, not just titles — and brief them); (c) live tests you can demo (show MFA enforcement, show audit-log review records, demonstrate tabletop results). Store evidence in a versioned repository with retention covering the assessment window.
8. **Address the people and process practices.** Technical teams underinvest here: security awareness training records (3.2.x), personnel screening (3.9.x), and maintenance procedures (3.7.x) all require *evidence of operation* — training completion logs, background-check records, maintenance tickets — not just policies. Start collecting these months before the assessment.
9. **Run an internal mock assessment.** Engage an independent party (internal audit or a consultant who is not the implementer) to walk the full practice set using the CMMC assessment-guide methodology (examine/interview/test per practice). Treat every mock finding as a real finding and remediate. A clean mock is your go/no-go gate for scheduling the real thing.
10. **Select and engage a C3PAO.**
    Verify the C3PAO's authorization status, agree on scope and schedule,
    complete pre-assessment readiness reviews, and align on
    evidence-submission mechanics.
    Do not schedule the real assessment until the mock is clean and POA&M
    items are within allowed bounds.
11. **Execute the assessment.**
    Support the assessment team with evidence access, interviewees, and test
    demonstrations.
    Log every assessor request and your response; this record is invaluable
    if findings are disputed and becomes the template for the next cycle.
    Keep daily internal syncs during the assessment to catch emerging issues
    early.
12. **Sustain compliance.**
    CMMC Level 2 requires annual affirmations and reassessment every three
    years.
    Convert assessment evidence collection into recurring operations:
    quarterly access reviews, continuous control monitoring, annual policy
    review, POA&M tracking to closure, yearly training refresh.
    Assign a permanent owner — compliance decays without one.

## Key tools & commands

- GRC platform or structured workbook (spreadsheet with the 110 practices)
  — the traceability matrix is the program backbone; keep it versioned.
- NIST SP 800-171 Rev 2 (the practice source) and the CMMC Level 2
  assessment guide (examine/interview/test objects per practice).
- Vulnerability scanner (e.g., Nessus/OpenVAS) and configuration baselines
  (STIGs/CIS Benchmarks) — evidence for System & Information Integrity and
  System & Communications Protection families.
- SIEM / centralized logging with documented review procedures — evidence
  for audit (3.3.x) and incident response (3.6.x).
- MFA and FIPS-validated cryptography inventory — evidence for 3.5.3 and
  3.13.11.
- Ticketing/HR systems — evidence for maintenance, personnel security, and
  training practices.

## Expected outputs

- A frozen scope package: boundary diagram, asset inventory, data-flow
  description for CUI, and the enclave decision record.
- A completed 110-practice traceability matrix with evidence pointers and
  named owners.
- An SSP that an assessor can read without follow-up questions on
  implementation detail.
- A POA&M with dated milestones, a mock-assessment report with remediation
  records, and (at the end) the C3PAO assessment result and sustainment plan
  with a permanent owner.

## Pitfalls

- Scoping too broadly inflates cost; scoping too narrowly fails the
  assessment. Get the enclave boundary right before spending on controls.
- "Inherited" practices (from a cloud provider) still require *your*
  evidence that the inheritance is configured and monitored — a vendor's
  attestation alone is not enough. Document shared responsibility explicitly.
- Treating compliance as a paperwork exercise: assessors *test* controls. An
  MFA policy nobody enforces will fail, and they will try to log in without it.
- Letting evidence go stale between the mock and the real assessment;
  re-validate evidence freshness in the final two weeks.
- Underestimating the people/process practices — they cause a
  disproportionate share of findings relative to implementation cost.
- Scheduling the C3PAO before the program is ready "to create urgency" —
  it creates a failed assessment record instead. The mock is the gate.

## References

- DoD CMMC program documentation (32 CFR Part 170; CMMC model and scoping
  guidance) — always verify currency against the current rulemaking
- NIST SP 800-171 Rev 2, "Protecting Controlled Unclassified Information in
  Nonfederal Systems and Organizations"
- NIST SP 800-171A (assessment procedures companion to 800-171)
- CMMC Assessment Process (CAP) and Level 2 assessment guide (examine /
  interview / test objects)
- CMMC scoping guidance (asset categorization: CUI, security-protection,
  contractor risk-managed, specialized)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
