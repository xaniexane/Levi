---
skill_id: legal_estate_planning
name: Estate Planning and Probate Basics
description: Wills, revocable trusts, powers of attorney, and how Illinois probate administration actually works.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1648, https://www.law.cornell.edu/uscode/text/26/2001]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [estate, probate, wills, trusts, illinois, succession]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about estate planning concepts with Illinois specifics. It is not
> legal advice, creates no attorney–client relationship, and does not substitute
> for a licensed attorney. Estate documents must be drafted or reviewed by
> counsel licensed in the relevant state.

# Estate Planning and Probate Basics

## Purpose

Cover the core instruments — wills, revocable living trusts, powers of
attorney, advance directives — and how Illinois probate administration
works when someone dies with or without them. This is the foundation
under the dynasty layer (`legal_dynasty_trusts` builds the long-duration
structures on top).

## The doctrine

- **Wills (Illinois Probate Act, 755 ILCS 5):** require testamentary
  capacity, writing, and attestation by two credible witnesses (755 ILCS
  5/4-3). Holographic (handwritten, unwitnessed) wills are *not* valid
  in Illinois. Wills go through probate — court-supervised, public,
  and slow — which is why trusts are popular.
- **Revocable living trusts:** the grantor transfers assets to a trust,
  retains full control during life, and avoids probate on those assets
  at death. Revocable trusts do *not* save estate tax or protect against
  creditors during the grantor's life — they buy privacy and speed, not
  tax or asset-protection benefits.
- **Powers of attorney:** Illinois statutory POA forms cover property
  (755 ILCS 45/2) and health care (755 ILCS 45/4). A POA dies with the
  principal — it is a disability-planning tool, not a death-planning one.
- **Beneficiary designations** (retirement accounts, life insurance,
  transfer-on-death instruments) pass *outside* probate and *override*
  the will — stale designations are the most common estate-planning
  failure.
- **Federal transfer tax (26 U.S.C. §§ 2001+):** estates above the
  lifetime exemption face estate tax; Illinois has its own estate tax
  with a lower exemption than the federal one — Illinois exposure can
  exist with zero federal exposure.
- **Intestacy:** dying without a will sends assets through the
  statutory heir hierarchy (755 ILCS 5/2-1) — the state's plan, not yours.

## Checklist

1. **Execute the four basics:** will (or trust-centered plan),
   revocable trust if probate avoidance matters, property POA, health
   care POA + living will.
2. **Fund the trust.** An unfunded trust is an empty bucket — retitle
   real estate, accounts, and business interests into it.
3. **Audit beneficiary designations** on every account and policy;
   align them with the plan (and name contingent beneficiaries).
4. **Name guardians** for minor children in the will — the one thing a
   trust cannot do.
5. **Plan for digital assets.** Illinois has adopted a version of the
   Revised Uniform Fiduciary Access to Digital Assets Act — grant
   explicit authority over digital accounts and cryptographic keys in
   the instruments.
6. **Review on life events:** marriage, divorce, births, deaths, moves
   across state lines, major asset changes — and at least every 3–5 years.

## Red flags

- A will drafted decades ago in another state, never reviewed after
  moving to Illinois.
- Trust created but never funded — the probate it was meant to avoid
  happens anyway.
- Beneficiary designations naming an ex-spouse or a deceased person.
- DIY documents for blended families, special-needs beneficiaries, or
  taxable estates — the failure modes are expensive.
- No plan for who controls crypto keys, business logins, and revenue
  accounts on incapacity.

## Authorities

- Illinois Probate Act, 755 ILCS 5:
  https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1648
- 26 U.S.C. § 2001 (estate tax imposed):
  https://www.law.cornell.edu/uscode/text/26/2001
- Illinois statutory POA forms: https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1504
