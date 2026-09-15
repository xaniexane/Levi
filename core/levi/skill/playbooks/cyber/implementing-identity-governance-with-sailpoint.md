---
skill_id: cyber_implementing_identity_governance_with_sailpoint
name: Implementing Identity Governance with SailPoint
description: Stand up identity governance with SailPoint — authoritative source integration, account aggregation, access certifications, and joiner-mover-leaver automation.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, governance, iga, sailpoint]
version: 1.0.0
---
## Purpose

Establish an identity governance program on SailPoint (Identity Security Cloud or IdentityIQ) that answers the core question — who has access to what, and should they — continuously rather than once a year in a spreadsheet. The playbook covers connecting authoritative sources, aggregating accounts, running certifications, and automating joiner-mover-leaver (JML) lifecycle events.

## When to use

- Standing up identity governance for the first time, or replacing manual access reviews.
- Preparing for audits (SOX, ISO 27001, PCI DSS) that require evidence of periodic access review.
- Reducing standing privileged access by tying entitlements to roles and employment status.
- Cleaning up orphaned, dormant, or duplicate accounts after a merger or rapid growth.
- Implementing segregation-of-duties (SoD) enforcement for finance, HR, and other regulated functions.

## Prerequisites

- An authoritative identity source (HR system such as Workday or SAP SuccessFactors) with reliable joiner/mover/leaver data — governance is only as good as this feed.
- Inventory of target systems to onboard: Active Directory, Entra ID, key SaaS apps, databases, and privileged vaults.
- Defined roles model (business roles, IT roles) drafted with application owners; do not let the tool invent roles from raw entitlements alone.
- Executive sponsor and named application owners who will actually complete certifications.
- Service accounts and API credentials for each source/target connector, scoped to read (and later write) only what the connector needs.

## Procedure

1. **Connect the authoritative source.** Integrate the HR system as the identity cube source of truth. Validate that hires, transfers, and terminations flow in with correct effective dates before connecting anything else — lifecycle automation built on stale HR data de-provisions the wrong people.
2. **Aggregate accounts and correlate identities.** Onboard connectors for AD, Entra ID, and priority applications. Correlate accounts to identities using deterministic rules (employee ID first, then email/username patterns). Review uncorrelated accounts manually; they are often service accounts, vendors, or ghosts.
3. **Build the role model.** Define business roles from job functions with HR and managers, then map them to IT roles/entitlements with application owners. Start with the top 10–20 roles covering 80% of the workforce; mine the remainder from entitlement patterns but validate each with an owner.
4. **Implement JML workflows.** Configure joiner provisioning (day-one access from role), mover re-certification on transfer (remove old entitlements, grant new), and leaver de-provisioning with tight SLAs (same-day for privileged, 24h for standard). Test with synthetic HR events before go-live.
5. **Launch access certifications.** Start with high-risk scopes: privileged accounts, SoD-conflicting entitlements, then application owners. Schedule quarterly for privileged and semi-annual for standard access. Track completion rates and escalate non-responders — an uncertified campaign is an audit finding.
6. **Enforce segregation of duties.** Define SoD policies (e.g., cannot hold both "create vendor" and "approve payment") and run them preventatively at request time plus detective scans on the existing population. Remediate conflicts with mitigation controls where removal is not immediately possible.
7. **Automate access requests and approvals.** Replace ticket-based access grants with catalog-driven requests routed to data owners, with policy checks (SoD, risk scoring) applied before approval. Log every decision for audit.
8. **Operationalize reporting.** Build dashboards for certification compliance, orphaned accounts, dormant privileged accounts, and SoD violations. Review monthly with the security team and quarterly with leadership.

## Expected outputs

- SailPoint tenant/instance connected to HR and priority systems with correlated identity cubes.
- Documented role model with owner sign-off.
- Working JML automation with measured provisioning/de-provisioning SLAs.
- Completed certification campaigns with evidence retained for audit.
- SoD policy set with preventive and detective controls.
- Monthly identity-governance metrics dashboard.

## Pitfalls

- **Garbage HR feed.** Duplicate employee records, missing termination dates, or contractors absent from HR silently break every downstream control. Fix the source before tuning the tool.
- **Boiling the ocean on roles.** Attempting a perfect enterprise role model delays value for a year. Ship the top roles, automate JML, and iterate.
- **Rubber-stamp certifications.** Managers approving hundreds of line items in minutes is theater. Scope campaigns tightly, provide last-used data, and flag high-risk items for real review.
- **Orphaned service accounts.** Non-human accounts fall outside HR-driven JML and accumulate. Maintain a separate service-account inventory with owners and rotation schedules.
- **Connector privilege creep.** Aggregation connectors with domain-admin-level rights become prime targets; scope them minimally and vault their credentials.

## References

- SailPoint product documentation — https://documentation.sailpoint.com/
- NIST SP 800-63-4, "Digital Identity Guidelines" — https://csrc.nist.gov/publications/detail/sp/800-63/4/final
- MITRE ATT&CK T1078 (Valid Accounts) — https://attack.mitre.org/techniques/T1078/
- ISO/IEC 27001:2022 Annex A controls 5.15–5.18 (access control) — standard via ISO
