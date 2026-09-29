---
skill_id: legal_employment_basics
name: Employment Law Fundamentals
description: At-will employment, wage/hour basics, anti-discrimination frameworks, and the Illinois overlay employers must know.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.law.cornell.edu/uscode/text/29/206, https://www.law.cornell.edu/uscode/text/42/2000e-2, https://www.dol.gov/agencies/whd/flsa]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [employment, flsa, discrimination, illinois, wage]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US employment law with Illinois specifics. It is not legal
> advice, creates no attorney–client relationship, and does not substitute for
> a licensed attorney. Personnel decisions with legal risk require counsel.

# Employment Law Fundamentals

## Purpose

Cover the employment-law baseline for anyone who hires: the at-will rule
and its exceptions, federal wage/hour duties, anti-discrimination
frameworks, leave law, and the Illinois statutes that layer on top of
federal law. Misclassification is handled in `legal_worker_classification`.

## The doctrine

- **At-will employment** is the US default: either side may end the
  relationship at any time for any lawful reason. Exceptions: contracts
  (including implied contracts from handbooks in some states),
  collective-bargaining agreements, and the public-policy, implied-
  covenant, and statutory exceptions — notably anti-retaliation
  protections, which are broad and heavily litigated.
- **FLSA (29 U.S.C. §§ 201–219):** federal minimum wage, overtime at
  1.5x for hours over 40/week for nonexempt workers, child-labor limits.
  Exemptions (executive, administrative, professional, outside sales,
  computer employees) turn on *duties performed*, not job titles, plus
  a salary-basis and salary-threshold test. Misclassifying nonexempt
  workers as exempt is among the costliest common violations.
- **Title VII (42 U.S.C. §§ 2000e–2000e-17):** bars employment
  discrimination on race, color, religion, sex, national origin (15+
  employees). The **Illinois Human Rights Act** (775 ILCS 5) extends
  further — lower employee threshold, additional protected classes.
- **ADA, ADEA, GINA, PDA** add disability, age (40+), genetic
  information, and pregnancy protections; the **FMLA** provides up to 12
  weeks of unpaid job-protected leave for covered employers/employees.
- **Illinois overlay:** Illinois Wage Payment and Collection Act (820
  ILCS 115) — final-pay timing and authorized-deduction rules are
  stricter than many states; Illinois Biometric Information Privacy Act
  (BIPA) imposes consent and retention duties on biometric identifiers
  (fingerprints, face geometry) with a private right of action; the
  Illinois Freedom to Work Act (820 ILCS 90) sharply limits non-competes.

## Checklist

1. **Classify before you hire.** Employee vs. contractor analysis first
   (see `legal_worker_classification`); then exempt vs. nonexempt for
   employees.
2. **Write the handbook carefully.** It should disclaim contract status
   explicitly or it may create one; include anti-harassment, complaint,
   and at-will acknowledgment provisions.
3. **Audit wage practices.** Timekeeping accuracy, overtime computation,
   lawful deductions (Illinois requires written employee consent for
   most deductions), final-pay deadlines on separation.
4. **Build the complaint channel.** Harassment/discrimination complaints
   need a documented intake, prompt investigation, and no retaliation —
   retaliation claims are easier for plaintiffs to win than the
   underlying discrimination claims.
5. **Check biometric touchpoints.** Any fingerprint timeclock, face-login,
   or voiceprint triggers BIPA's written-consent and retention-schedule
   duties *before* collection.
6. **Calendar leave and posting duties.** FMLA administration, required
   workplace postings (federal + Illinois), new-hire reporting.

## Red flags

- "Everyone's salary, so no overtime" — salary alone never creates an
  exemption; duties and thresholds do.
- Handbook promising "termination only for cause" while claiming at-will
  elsewhere.
- Deductions from final paychecks for alleged debts without written
  authorization — an Illinois Wage Payment Act violation pattern.
- Biometric timeclocks deployed with no BIPA consent process.
- Treating retaliation as a lesser risk — it is statistically the
  most successful employment claim.

## Authorities

- 29 U.S.C. § 206 (minimum wage): https://www.law.cornell.edu/uscode/text/29/206
- 42 U.S.C. § 2000e-2 (unlawful employment practices):
  https://www.law.cornell.edu/uscode/text/42/2000e-2
- DOL FLSA guidance: https://www.dol.gov/agencies/whd/flsa
- EEOC guidance: https://www.eeoc.gov/laws-guidance
- Illinois Human Rights Act, 775 ILCS 5:
  https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=2266
