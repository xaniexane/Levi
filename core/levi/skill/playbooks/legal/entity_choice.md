---
skill_id: legal_entity_choice
name: Entity Choice — Corporation, LLC, and S-Corp Trade-offs
description: Comparing C-corps, S-corps, and LLCs on liability, taxation, and governance, with Delaware and Illinois notes.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.law.cornell.edu/uscode/text/26/1361, https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1785, https://www.irs.gov/businesses/small-businesses-self-employed/s-corporations]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [entity, llc, corporation, s-corp, formation, tax]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US business-entity law. It is not legal advice, creates no
> attorney–client relationship, and does not substitute for a licensed attorney
> or CPA. Entity and tax elections should be reviewed by counsel and a tax
> professional.

# Entity Choice — Corporation, LLC, and S-Corp Trade-offs

## Purpose

Compare the three workhorse entities on the dimensions that decide real
outcomes: liability shield, tax treatment, governance burden, and
investor compatibility. Default jurisdiction notes cover Delaware (the
corporate standard) and Illinois (home ground: 805 ILCS 5 Business
Corporation Act, 805 ILCS 180 Limited Liability Company Act).

## The doctrine

- **C-corporation:** separate taxpayer; profits taxed at the entity level
  (21% federal) and again on dividends — the "double tax." Best for
  venture-scale fundraising (investors expect Delaware C-corps), stock
  option plans, and eventual acquisition. Governance is formal: board,
  officers, bylaws, minutes.
- **S-corporation (26 U.S.C. §§ 1361–1379):** pass-through taxation with
  corporate form. Strict eligibility: 100-shareholder cap, one class of
  stock, US individuals/qualifying trusts/estates only — no partnerships,
  corporations, or nonresident aliens as shareholders. Election via Form
  2553. Saves self-employment tax on distributions (salary still subject
  to payroll tax — the IRS watches unreasonably low officer salaries).
- **LLC:** pass-through by default (disregarded or partnership), liability
  shield, contractual governance via operating agreement. Flexible profit
  splits divorced from ownership percentages. Downsides: self-employment
  tax on active members' distributive shares, awkward for VC equity
  rounds and option plans, and state-law variance (charging-order
  protections differ).
- **Liability shield (all three):** the entity, properly maintained, is
  liable — not the owners. The shield fails through veil-piercing:
  commingling funds, ignoring formalities, undercapitalization, using the
  entity to commit wrongs. Single-member LLCs get less deference in some
  courts.
- **Delaware vs. Illinois:** Delaware offers the Court of Chancery and
  deep case law — the investor standard. Illinois entities avoid Delaware
  franchise tax and foreign-qualification cost for a home-state business;
  Illinois LLCs file annual reports with the Secretary of State.

## Checklist

1. **Match entity to capital plan.** Seeking venture money → Delaware
   C-corp. Bootstrapped/profit-distributing → LLC or S-corp.
2. **Run the tax math with a CPA.** Model double-tax vs. pass-through vs.
   S-corp payroll-tax savings on *your* numbers, including Illinois
   Personal Property Replacement Tax angles for S-corps.
3. **Form correctly.** Articles/certificate filed with the Secretary of
   State; EIN from the IRS; S-election within the deadline if applicable.
4. **Govern from day one.** Operating agreement or bylaws signed, initial
   resolutions, capitalization table, separate bank account — the
   formalities that keep the veil intact.
5. **Qualify where you operate.** Doing business in another state
   requires foreign qualification there; skipping it risks fines and
   inability to sue in that state's courts.

## Red flags

- Operating for months with no governing document signed.
- Personal and business funds in one account — the fastest way to pierce
  the veil.
- Electing S-corp without checking shareholder eligibility (one
  ineligible shareholder terminates the election).
- Forming in Delaware "because startups do" while operating solely in
  Illinois — paying two states' fees for no benefit.
- Assuming an LLC shields against *professional* liability or personal
  torts — it shields entity debts, not your own wrongs.

## Authorities

- 26 U.S.C. §§ 1361–1379 (S corporations):
  https://www.law.cornell.edu/uscode/text/26/1361
- Illinois LLC Act, 805 ILCS 180:
  https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1785
- IRS S-corporation guidance:
  https://www.irs.gov/businesses/small-businesses-self-employed/s-corporations
- Illinois Secretary of State business services: https://www.ilsos.gov/
