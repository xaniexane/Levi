---
skill_id: legal_trade_secrets
name: Trade Secret Protection — DTSA and Illinois Law
description: What qualifies as a trade secret, the "reasonable measures" requirement, NDAs, and misappropriation remedies under federal and Illinois law.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.law.cornell.edu/uscode/text/18/1836, https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1417]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [trade-secrets, dtsa, nda, ip-protection, illinois]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal and Illinois trade-secret law. It is not legal
> advice, creates no attorney–client relationship, and does not substitute for
> a licensed attorney. Trade-secret programs should be reviewed by counsel.

# Trade Secret Protection — DTSA and Illinois Law

## Purpose

Protect the unreplicable: algorithms, training corpora, methods, customer
lists, and dynasty IP that must never be published or patented. Covers
what qualifies as a trade secret, the reasonable-measures duty that makes
or breaks every claim, NDA practice, and remedies under the Defend Trade
Secrets Act (DTSA) and the Illinois Trade Secrets Act (765 ILCS 1065).

## The doctrine

A trade secret is information that (1) derives independent economic value
from not being generally known or readily ascertainable, and (2) is
subject to reasonable measures to maintain secrecy (18 U.S.C. § 1839(3);
765 ILCS 1065/2(d)). No registration exists — protection lasts as long as
secrecy lasts, but it evaporates the moment secrecy does.

- **DTSA (2016)** created a federal civil cause of action (18 U.S.C.
  § 1836(b)), including ex parte seizure in extraordinary cases,
  injunctions, actual damages, unjust enrichment, exemplary damages up to
  2x for willful and malicious misappropriation, and attorney's fees.
  State-law claims (like the Illinois Act) coexist; plaintiffs routinely
  plead both.
- **Reasonable measures are the whole game.** Courts deny trade-secret
  status to information the owner treated casually. Measures scale with
  value: access controls, need-to-know partitioning, marking, NDAs,
  exit interviews, logging.
- **Misappropriation** = acquisition by improper means, or disclosure/use
  in breach of a duty (765 ILCS 1065/2(b)). Independent discovery and
  reverse engineering are *not* improper means.
- **Inevitable disclosure:** Illinois recognizes the doctrine (e.g.,
  *PepsiCo v. Redmond*) — a former employee may be enjoined from a new
  role where trade-secret use is genuinely inevitable. It is an
  extraordinary remedy, not a routine non-compete substitute, and its
  availability varies by jurisdiction.
- **Whistleblower immunity (18 U.S.C. § 1833(b)):** employees/contractors
  have immunity for disclosing trade secrets to the government or in
  sealed court filings to report legal violations — and employers must
  give notice of this immunity in covered agreements or lose exemplary
  damages and fees under the DTSA.

## Checklist

1. **Identify and inventory.** List what is actually secret and valuable
   (not everything — overclaiming weakens the real claims).
2. **Mark it.** Confidential legends on documents, repositories, and
   datasets; classification tiers for the crown jewels.
3. **Control access.** Need-to-know partitioning, authentication, logging;
   contractors get scoped access, never the vault.
4. **Paper the relationships.** NDAs with everyone who touches secrets —
   employees, contractors, collaborators — including the § 1833(b)
   whistleblower notice; invention-assignment clauses for creators.
5. **Run the exits.** Exit interviews reminding of continuing duties,
   credential revocation same-day, return-of-materials certification.
6. **Mind the clock.** DTSA/Illinois limitations periods run from
   discovery of misappropriation — investigate promptly when leakage is
   suspected.

## Red flags

- "Our NDA" is a downloaded template with no whistleblower-immunity
  notice — DTSA exemplary damages and fees are then unavailable.
- Secrets shared in chat threads, screenshots, or personal devices with
  no controls.
- No exit process — departing contractors keep repo access for months.
- Treating trade-secret protection and patenting as interchangeable —
  they are opposites (disclosure vs. secrecy).
- Assuming an NDA alone creates a trade secret — without reasonable
  measures, courts find no protectable secret regardless of the paper.

## Authorities

- 18 U.S.C. § 1836 (DTSA civil action):
  https://www.law.cornell.edu/uscode/text/18/1836
- 18 U.S.C. § 1839 (definitions): https://www.law.cornell.edu/uscode/text/18/1839
- Illinois Trade Secrets Act, 765 ILCS 1065:
  https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=1417
- 18 U.S.C. § 1833(b) (whistleblower immunity):
  https://www.law.cornell.edu/uscode/text/18/1833
