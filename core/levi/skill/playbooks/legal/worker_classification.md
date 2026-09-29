---
skill_id: legal_worker_classification
name: Worker Classification — Employee vs. Independent Contractor
description: The ABC test, the economic-reality test, and Illinois-specific classification rules for contractors.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.dol.gov/agencies/whd/flsa/misclassification, https://www.law.cornell.edu/uscode/text/26/3509]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [employment, classification, contractor, abc-test, illinois]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US worker-classification law. It is not legal advice, creates
> no attorney–client relationship, and does not substitute for a licensed
> attorney. Classification decisions carry back-tax, benefit, and penalty
> exposure — get counsel involved before engaging contractors at scale.

# Worker Classification — Employee vs. Independent Contractor

## Purpose

Answer the classification question correctly before anyone starts work:
is this person an employee or an independent contractor? Covers the
competing tests (ABC, economic reality), the Illinois-specific rules,
and the consequences of getting it wrong — which include back taxes,
overtime liability, and benefits exposure.

## The doctrine

No single test governs everywhere; different statutes apply different
tests, and a worker can be a contractor under one law and an employee
under another.

- **The ABC test** (used in many states for unemployment/wage claims,
  and in Illinois under the Wage Payment and related statutes): the
  worker is an employee unless the hiring party proves (A) freedom from
  control, (B) the work is outside the usual course of the hiring
  party's business, and (C) the worker is engaged in an independently
  established trade. Prong B is the killer for platform and agency
  models — if contractors do your core business, they fail it.
- **The economic-reality test** (FLSA): courts weigh control, opportunity
  for profit/loss, investment, permanence, nature of control, and
  integration into the business. The DOL's rulemakings have swung between
  emphasis points — check the *current* final rule, not commentary about
  proposed ones.
- **The common-law control test** (NLRA, many tax contexts): the
  traditional multi-factor control analysis; the IRS's 20-factor
  formulation (now condensed) still informs practice.
- **Illinois specifics:** Illinois applies strict classification tests
  in the wage-payment and unemployment-insurance contexts; the
  Illinois Employee Classification Act targets construction and related
  industries with its own framework. Assume Illinois is stricter than
  the federal floor.
- **Consequences of misclassification:** back payroll taxes with
  penalties and interest, overtime and benefits liability, workers'
  compensation exposure, and in willful cases, personal liability for
  responsible officers.

## Checklist

1. **Test under every applicable statute.** FLSA, state wage law,
   unemployment insurance, workers' comp, tax — run each test
   separately; passing one does not pass the others.
2. **Document the business reality.** Written contractor agreement
   (scope, term, payment terms, IP assignment), the contractor's
   independent business indicia (other clients, business cards,
   separate office/equipment, profit/loss exposure).
3. **Do not control the how.** Assign outcomes and deadlines, not
   schedules, methods, and tools — day-to-day control is the fact
   pattern that loses cases.
4. **Re-test on change.** A contractor who starts full-time, on-site,
   supervised, and exclusive has usually become an employee whatever
   the agreement says.
5. **Consider voluntary reclassification programs** (e.g., IRS
   settlement programs) before an audit forces the question — with
   counsel, not alone.

## Red flags

- Full-time, indefinite, supervised, on-site "contractors" doing the
  company's core work — fails prong B almost everywhere it applies.
- Requiring contractors to work set hours, attend standups, and use
  company equipment while calling them contractors.
- One contractor agreement template used for everyone from the
  copywriter to the core engineer.
- "1099 them and it's settled" — labels in the agreement do not
  control; the working relationship does.
- Ignoring state law because the federal test seemed passable.

## Authorities

- DOL misclassification guidance:
  https://www.dol.gov/agencies/whd/flsa/misclassification
- 26 U.S.C. § 3509 (employment-tax treatment):
  https://www.law.cornell.edu/uscode/text/26/3509
- Illinois Department of Employment Security — worker classification:
  https://ides.illinois.gov/
