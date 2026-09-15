---
skill_id: cyber_implementing_gdpr_data_subject_access_request
name: GDPR Data Subject Access Request (DSAR) Handling
description: Build a repeatable DSAR workflow: intake, verification, discovery, redaction, and on-time delivery.
risk: info
permissions: []
requires_confirmation: false
tags: [privacy, compliance]
version: 1.0.0
---
## Purpose
Data subjects can demand to know what you hold about them — and you have 30 days to deliver a
complete, accurate response. Manual DSAR handling (email threads, spreadsheet tracking, ad-hoc
database queries) misses data, blows deadlines, and creates regulatory exposure. This playbook
builds the DSAR workflow: intake, identity verification, systematic discovery, third-party
redaction, and delivery — repeatable and auditable.

## When to use
- Operationalizing GDPR/CCPA data-subject rights (access, and by extension erasure/portability).
- After missed DSAR deadlines, incomplete responses, or regulatory complaints.
- Before scaling: request volumes grow with awareness — build the machine before the flood.
- When auditors or customers ask to see the rights-fulfillment process.
- As the rights-execution arm of the GDPR controls program.

## Prerequisites
- Defined scope: which rights you support and the intake channels (web form, email, privacy portal).
- Data inventory / RoPA: you can't find personal data you haven't mapped to systems.
- Identity-verification procedure proportionate to the data's sensitivity (and fraud-aware — DSARs
  are a social-engineering vector).
- Legal review of response templates, redaction standards, and extension criteria.
- Tooling: a DSAR case tracker (ticketing with SLA clocks) and data-discovery/search capability.

## Procedure
1. **Stand up intake with an SLA clock.** Every request gets a case on receipt: timestamp starts the
   30-day clock (EU) immediately. Acknowledge within a few business days with: what happens next,
   the verification step, and the expected timeline. Intake channels monitored daily — a request
   sitting in an unmonitored inbox still counts against the deadline.
2. **Verify identity proportionately.** Match the verification rigor to the data's sensitivity:
   account-holder verification via existing auth for logged-in requests; document checks for
   high-sensitivity data. Watch for fraudulent DSARs (attackers requesting others' data) —
   verification failures get documented refusal with reasoning, not silent drops.
3. **Scope and clarify promptly.** Confirm: which rights are invoked, the time period, and any
   specific systems if the requester narrows it. If the request is unclear, ask for clarification
   immediately (the clock may pause per local guidance — confirm with counsel). Log all scope
   decisions.
4. **Discover systematically across the inventory.** Query every in-scope system from the RoPA:
   production databases, data warehouses, backups (note recoverability limits honestly), SaaS apps,
   email/archives, logs, and unstructured shares. Use e-discovery/search tooling where available.
   Document systems searched and queries run — "we searched everywhere relevant" needs evidence.
5. **Redact third-party data.** Remove or redact other individuals' personal data from the response
   (colleagues in emails, other customers in shared records) unless you have a basis to disclose.
   Apply legal-privilege and trade-secret exclusions per counsel's guidance, noting the exclusion
   category (not the content) to the requester.
6. **Compile the response package.** Include: the personal data (organized by category/system, in an
   intelligible format), plus the required information — purposes, categories, recipients, retention
   periods, rights available, and complaint route. Provide in a commonly used electronic format for
   portability where applicable.
7. **Quality-check before delivery.** A second reviewer verifies: completeness against the discovery
   log, correct redactions, no third-party leakage, and accurate supplementary information. Rushed
   DSARs leak other people's data — the review is the control.
8. **Deliver securely and document.** Send via a secure channel (authenticated portal or encrypted
   delivery — not plaintext email for sensitive data). Record: delivery date, method, and contents
   summary. Close the case only after confirmed delivery; follow up on bounce/failure.
9. **Handle the edge cases per policy.** Manifestly unfounded or excessive requests: document the
   reasoning, charge a fee or refuse per GDPR allowance, and inform of the complaint route. Complex
   cases: extend by two months with written notice before the initial deadline expires. Children's
   data, deceased persons, and employee-vs-customer distinctions: per counsel's playbook.
10. **Learn from every DSAR.** Track: volume by right type, SLA attainment, discovery gaps found
    (systems missing from the RoPA — fix the inventory), redaction errors, and requester complaints.
    Quarterly review with the DPO: are responses getting faster and more complete? Feed gaps back
    into data mapping and minimization.

## Expected outputs
- A tracked DSAR workflow: intake, verification, discovery, redaction, review, delivery — with SLA
  clocks.
- System-by-system discovery procedures tied to the RoPA, with search evidence per case.
- Redaction standards and second-reviewer quality control.
- Edge-case policies (excessive requests, extensions, fraud) with legal sign-off.
- Metrics: volume, SLA attainment, discovery gaps, complaints — reviewed quarterly.

## Pitfalls
- Ad-hoc handling: email-thread DSARs miss systems and deadlines. Case tracking with SLA clocks is
  the minimum viable process.
- Weak identity verification: fraudulent DSARs are a real attack — verify proportionately, document
  refusals.
- Incomplete discovery: responding from one database while five SaaS apps hold data is worse than a
  late response — it's a false complete response. Inventory-driven discovery.
- Skipping the second review: third-party data leakage in DSAR responses creates new breaches.
  Review every package.
- Ignoring erasure/portability siblings: the access workflow should extend to deletion and export —
  build once, reuse.

## References
- GDPR Articles 12-23 (data-subject rights, response obligations)
- EDPB guidelines on data-subject rights and response timeframes
- NIST Privacy Framework (individual participation controls)
- ISO/IEC 27701 (PIMS guidance on rights fulfillment)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
