---
skill_id: legal_business_tax
name: Business Taxation — Entity Tax and Self-Employment Tax
description: How C-corps, S-corps, partnerships, and sole proprietors are taxed, and where self-employment tax bites.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.irs.gov/businesses/small-businesses-self-employed/self-employment-tax-social-security-and-medicare-taxes, https://www.law.cornell.edu/uscode/text/26/1361]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [tax, business-tax, self-employment, s-corp, pass-through]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal tax concepts. It is not legal or tax advice, creates
> no attorney–client or accountant–client relationship, and does not substitute
> for a licensed attorney or CPA. Tax elections and filings require professional
> review. Rates and thresholds change — verify current figures with the IRS.

# Business Taxation — Entity Tax and Self-Employment Tax

## Purpose

Explain how the choice of entity changes the tax bill: who pays tax on
business income, when, and at what rate. Covers C-corp double taxation,
S-corp and partnership pass-through, sole-proprietor treatment, and the
self-employment tax that surprises first-time founders. Pairs with
`legal_entity_choice` (the legal form) and `legal_crypto_tax` (digital
assets).

## The doctrine

- **C-corporation:** the corporation pays federal income tax on its
  profits (flat 21%), and shareholders pay again on dividends. Retained
  earnings compound inside the corporation at the single entity-level
  rate — the trade-off for double taxation on distributions.
- **S-corporation:** pass-through — income flows to shareholders'
  personal returns whether or not distributed. Shareholder-employees must
  take reasonable salary subject to payroll tax; remaining distributions
  escape self-employment tax. The IRS recharacterizes unreasonably low
  salaries.
- **Partnership / multi-member LLC (default):** pass-through via Form
  1065 and Schedules K-1. Active partners/members generally owe
  self-employment tax on their distributive share of ordinary business
  income, not just on cash drawn.
- **Sole proprietorship / single-member LLC (default):** disregarded —
  income on Schedule C, subject to income tax *and* self-employment tax
  (Social Security + Medicare, per IRS guidance).
- **Self-employment tax** applies to net earnings from self-employment
  above the statutory threshold; it is separate from income tax and is
  often the larger surprise for new businesses.
- **Estimated tax:** pass-through owners generally must pay quarterly
  estimated tax (Form 1040-ES); underpayment triggers penalties.
- **Illinois layer:** Illinois imposes its own income tax on individuals
  and a Personal Property Replacement Tax structure affecting
  partnerships/S-corps — model state liability separately, not as an
  afterthought.

## Checklist

1. **Classify the entity's tax status explicitly.** Formation state law
   and federal tax elections are independent — an LLC can be taxed as a
   disregarded entity, partnership, S-corp, or C-corp.
2. **Model total tax, not just the rate.** Include self-employment/payroll
   tax, state tax, and the timing of distributions vs. allocations.
3. **Set reasonable salary early** for S-corp owner-employees;
   document the basis (role, hours, market data).
4. **Calendar estimated payments** (quarterly) and entity filings
   (1065, 1120-S, 1120 with their extensions).
5. **Keep immaculate books.** Commingled or reconstructed records turn
   every deduction into a negotiation; separate accounts from day one.
6. **Revisit annually.** Income level, owner count, and exit plans change
   the optimal election — what was right at $50k may be wrong at $500k.

## Red flags

- "LLC means no taxes" — the LLC is a legal form, not a tax status;
  default LLC taxation still taxes the income.
- Zero salary for a full-time S-corp owner — the IRS's favorite
  adjustment.
- Ignoring quarterly estimates until April — penalties plus a cash-flow
  shock.
- Deducting personal expenses through the business — substantiation
  rules (especially vehicles, travel, meals) are strict.
- Crypto or NFT proceeds treated as "not real income" — they are
  (see `legal_crypto_tax`).

## Authorities

- IRS self-employment tax guidance:
  https://www.irs.gov/businesses/small-businesses-self-employed/self-employment-tax-social-security-and-medicare-taxes
- 26 U.S.C. § 1361 (S corporation defined):
  https://www.law.cornell.edu/uscode/text/26/1361
- IRS S-corporation page:
  https://www.irs.gov/businesses/small-businesses-self-employed/s-corporations
- IRS estimated tax: https://www.irs.gov/businesses/small-businesses-self-employed/estimated-taxes
