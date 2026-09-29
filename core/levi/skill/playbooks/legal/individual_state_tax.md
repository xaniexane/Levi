---
skill_id: legal_individual_state_tax
name: Individual Income Tax and Illinois State Tax Basics
description: Federal individual income tax mechanics — filing, deductions, credits, estimated tax — plus Illinois income and sales-tax fundamentals.
category: legal
risk: info
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.irs.gov/filing, https://tax.illinois.gov/]
requires_attorney_review: false
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [tax, individual, illinois, filing, deductions]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal and Illinois tax concepts. It is not legal or tax
> advice, creates no professional relationship, and does not substitute for a
> licensed attorney or CPA. Rates, thresholds, and rules change — verify current
> figures with the IRS and the Illinois Department of Revenue.

# Individual Income Tax and Illinois State Tax Basics

## Purpose

Explain how individual income tax works at the federal level and what
Illinois adds on top: filing obligations, how taxable income is computed,
deductions vs. credits, estimated tax, and the Illinois flat income tax
and sales/use tax basics. Pairs with `legal_business_tax` (entity-level)
and `legal_crypto_tax` (digital assets).

## The doctrine

- **Federal structure:** gross income (§ 61 — "all income from whatever
  source derived," a deliberately broad definition) minus adjustments =
  adjusted gross income (AGI); minus the standard deduction or itemized
  deductions = taxable income; tax computed from the bracket tables;
  minus credits = tax owed. Deductions reduce *taxable income*; credits
  reduce *tax itself* — a dollar of credit is worth more than a dollar
  of deduction.
- **Filing:** most individuals file Form 1040 annually by April 15
  (extensions extend filing, not payment). Filing thresholds depend on
  status, age, and income type — self-employment income has its own low
  threshold.
- **Estimated tax:** employees have withholding; everyone else
  (contractors, business owners, investors) generally pays quarterly
  estimated tax to avoid underpayment penalties.
- **Illinois income tax:** a flat rate on federal AGI with Illinois
  modifications (verify the current rate — the legislature sets it, and
  it has changed). Illinois offers relatively few modifications; most
  federal AGI flows straight through.
- **Illinois sales and use tax:** imposed on retail sales of tangible
  personal property and certain services; marketplace-facilitator rules
  put collection duties on platforms. *Use tax* covers taxable purchases
  on which no sales tax was collected (e.g., out-of-state online buys) —
  legally owed by the buyer, widely underreported, occasionally audited.
- **Nexus:** physical presence or economic thresholds create filing and
  collection duties in a state; remote sellers and digital businesses
  must track where their customers are.

## Checklist

1. **Know your filing obligation** — status, income level, and income
   type each matter; when in doubt, file.
2. **Choose standard vs. itemized deliberately** each year — compare,
   don't default; bunching deductions across years can beat the
   standard deduction in alternate years.
3. **Track basis and records** for investments, crypto, and business
   income (see `legal_crypto_tax`).
4. **Pay estimates quarterly** if you lack withholding — calendar the
   four due dates.
5. **Model Illinois separately.** Flat-rate income tax on IL-modified
   AGI, plus sales/use-tax collection duties if you sell tangible goods
   or facilitator-covered services into Illinois.
6. **Keep returns and support** for at least the limitations period
   (generally 3 years from filing, longer for substantial understatement
   or fraud — keep longer, not shorter).

## Red flags

- "I'll settle up in April" with no withholding and no estimates —
   penalties plus a cash crunch.
- Confusing deductions with credits when evaluating tax strategies.
- Ignoring use-tax obligations on business purchases from out-of-state
  vendors.
- Assuming Illinois follows every federal provision — Illinois
  modifications decouple in places; check the IL-1040 instructions.
- Crypto, NFT, or side-business income treated as "not enough to matter"
  — the filing thresholds for self-employment income are low.

## Authorities

- IRS filing information: https://www.irs.gov/filing
- 26 U.S.C. § 61 (gross income defined):
  https://www.law.cornell.edu/uscode/text/26/61
- Illinois Department of Revenue: https://tax.illinois.gov/
- IRS estimated tax: https://www.irs.gov/businesses/small-businesses-self-employed/estimated-taxes
