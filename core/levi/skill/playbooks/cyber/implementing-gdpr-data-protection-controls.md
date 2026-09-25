---
skill_id: cyber_implementing_gdpr_data_protection_controls
name: GDPR Data Protection Controls
description: Implement GDPR-aligned data protection controls: records, DPIAs, rights, breach response, and evidence.
risk: info
permissions: []
requires_confirmation: false
tags: [privacy, compliance]
version: 1.0.0
---
## Purpose
GDPR compliance isn't a policy document — it's operational controls: knowing what personal data you
hold and why, protecting it appropriately, honoring data-subject rights on time, and notifying
breaches within 72 hours. This playbook implements the control set that makes GDPR real: records of
processing, DPIAs, rights workflows, breach response, and the evidence regulators expect. (This is
operational guidance, not legal advice — involve counsel.)

## When to use
- Building or maturing a GDPR compliance program for EU personal data processing.
- After regulatory inquiries, complaints, or incidents involving personal data.
- Before launching products or entering markets that process EU residents' data.
- Meeting customer/partner due-diligence expectations on privacy.
- As the privacy-governance layer above technical controls (encryption, DLP, access control).

## Prerequisites
- Defined scope: which processing activities involve EU personal data (start with the RoPA — you
  can't protect what you haven't inventoried).
- Executive ownership: a DPO (or responsible owner) with authority, and legal counsel engaged.
- Data inventory: systems, vendors, and data flows involving personal data.
- Technical controls baseline: encryption, access control, logging (GDPR's "appropriate technical
  measures" need actual implementation).
- Vendor/processor inventory with contract status (DPAs in place or not).

## Procedure
1. **Build the Record of Processing Activities (RoPA).** For each processing activity: purpose,
   lawful basis, data categories, data subjects, recipients/processors, retention period, and
   security measures. The RoPA is the program's foundation and the regulator's first request — keep
   it current, not ceremonial.
2. **Validate lawful bases and minimize.** For each activity, confirm the lawful basis actually fits
   (consent, contract, legitimate interests with balancing test documented, etc.). Eliminate data
   collected "just in case" — minimization is both a principle and a breach-blast-radius control.
   Document retention schedules and enforce deletion.
3. **Run DPIAs for high-risk processing.** Data Protection Impact Assessments for: new technologies,
   large-scale processing, systematic monitoring, and sensitive data. DPIA = describe processing,
   assess necessity, identify risks, define mitigations, consult DPO, review before launch. No
   high-risk launch without a completed DPIA.
4. **Implement data-subject rights workflows.** Build the intake-to-fulfillment process for: access
   (DSAR), rectification, erasure, portability, restriction, and objection — with identity
   verification, a 30-day SLA clock, and extension handling. (See the companion DSAR playbook for
   the detailed workflow.) Test it before the first real request.
5. **Establish the 72-hour breach response.** Playbook: detect → assess (is it personal data? risk
   to rights?) → contain → notify the supervisory authority within 72 hours if required → notify
   data subjects without undue delay if high risk → document everything (even non-notifiable
   breaches go in the register). Rehearse with a tabletop — the clock starts at awareness, not at
   understanding.
6. **Lock down processor relationships.** Inventory all processors/sub-processors; execute DPAs with
   required terms (processing only on instructions, confidentiality, assistance with rights,
   deletion/return, audit rights); verify sub-processor disclosures. No DPA = non-compliant
   processing — track to closure.
7. **Address cross-border transfers.** Map transfers outside the EEA; implement the appropriate
   mechanism (adequacy decision, SCCs, BCRs) plus transfer impact assessments where required.
   Document per transfer — regulators ask specifically about this.
8. **Implement privacy by design in engineering.** Require: DPIA triggers in the product-launch
   checklist, data-minimization review in design, default privacy-preserving settings, and
   retention/deletion built into data stores (not bolted on later). Privacy review gates in the SDLC
   make this systematic.
9. **Train and evidence.** Role-based training: all staff (basics, phishing, handling), engineers
   (design, minimization), and handlers of rights requests (procedure, SLA). Maintain the evidence
   pack: RoPA, DPIAs, rights logs, breach register, DPA inventory, training records, and
   technical-measure documentation.
10. **Review and report.** Annual program review (or on major changes): RoPA accuracy, DPIA
    completion, rights SLA performance, breach-register review, vendor compliance, and training
    completion. Report to leadership: compliance posture, open gaps, and regulatory developments.
    GDPR is continuous, not a project with an end date.

## Expected outputs
- A current RoPA with validated lawful bases, minimization, and retention enforcement.
- DPIA process with completed assessments for high-risk processing.
- Operational rights workflows meeting the 30-day SLA; tested breach response meeting 72 hours.
- Processor DPA inventory with transfer mechanisms documented.
- Privacy-by-design gates in engineering and a complete evidence pack.

## Pitfalls
- RoPA as a one-time spreadsheet: processing changes constantly; a stale RoPA misleads everyone
  including regulators. Assign ownership and review cadence.
- Consent as the default lawful basis: often the wrong basis (employment, B2B) and the hardest to
  manage. Choose the basis that actually fits, with counsel.
- Rights workflows that don't scale: manual DSAR handling collapses under volume. Build tooling for
  data discovery and export early.
- Breach notification decided by gut: the 72-hour assessment needs pre-defined criteria and a
  rehearsed team, not ad-hoc debate during an incident.
- Vendor DPAs ignored: "we have a DPA template" isn't the control — executed DPAs with sub-processor
  tracking is.

## References
- GDPR text (Regulation (EU) 2016/679) — Chapters II, III, IV, V
- EDPB guidelines (DPIAs, breach notification, lawful basis, data-subject rights)
- NIST Privacy Framework (operationalizing privacy controls)
- ISO/IEC 27701 (privacy information management)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
