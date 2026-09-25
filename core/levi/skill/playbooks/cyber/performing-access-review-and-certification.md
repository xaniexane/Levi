---
skill_id: cyber_performing_access_review_and_certification
name: Performing Access Review and Certification
description: Execute platform-agnostic access reviews that actually remove unnecessary access.
risk: info
permissions: []
requires_confirmation: false
tags: [identity, access-review, governance]
version: 1.0.0
---

## Purpose
This playbook defines a platform-agnostic access review and certification process: scoping reviews, enabling real reviewer decisions, enforcing revocations, and evidencing the cycle — applicable whether you use a dedicated IGA tool or structured manual campaigns.

## When to use
- Meeting recurring certification obligations without an expensive IGA suite.
- Privileged and sensitive-data access has never been systematically re-validated.
- Audit findings cite excessive or orphaned access.

## Prerequisites
- Authoritative identity source (HR) and entitlement data per in-scope system.
- Named reviewers with accountability: managers, application owners, or data owners.
- Revocation capability: someone who can actually remove access when denied.

## Procedure
1. **Scope by risk.** Prioritize privileged accounts, financial systems, customer data stores, and dormant accounts; document what is in and out of scope each cycle.
2. **Build reviewer-ready data.** For each entitlement show: who has it, what it grants (in plain language), last used date where available, and how it was granted.
3. **Set the decision standard.** Instruct reviewers: certify only access the person needs for their current role; "not sure" means investigate, not approve.
4. **Run the campaign.** Distribute review packages with deadlines; track completion and chase non-responders through their management chain.
5. **Enforce revocations.** Remove denied access within the defined window and verify removal; log every revocation with date and verifier.
6. **Handle exceptions.** Document business-justified exceptions with expiry dates and compensating controls; re-review them every cycle.
7. **Evidence the cycle.** Archive reviewer decisions, completion records, and revocation verification for auditors; report metrics to governance.

8. **Review service accounts separately.** Non-human accounts accumulate the most dangerous access and have no manager to review them; assign technical owners and review on a shorter cycle.
9. **Connect to provisioning.** Feed review outcomes back into joiner-mover-leaver logic; if movers keep the wrong access, the review is treating symptoms.

## Expected outputs
- Review packages with plain-language entitlement descriptions and usage data.
- Certification records: decisions, reviewers, dates, revocations verified.
- Metrics: coverage, on-time completion, access removed, exception inventory.
- Example: reviewers receive a package showing each entitlement, its last-used date, and a plain-language description; 8% of entitlements are denied and removed within 5 business days with verification.

## Pitfalls
- Reviewing without "last used" data, forcing reviewers to certify blindly.
- No-show reviewers with no escalation: the campaign quietly dies.
- Certifications filed while denied access is never actually removed.

- Reviews conducted by people who do not understand the entitlements; invest in descriptions or accept that the review is theater.
- Treating contractor and vendor access with the same annual cycle as employees; third-party access deserves more frequent review.

## References
- NIST SP 800-53 Rev. 5, control AC-2 (account management).
- ISO/IEC 27001:2022, Annex A control 5.17 (authentication information) and 8.5 (secure authentication).
- ISACA COBIT guidance on access management reviews.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
