---
skill_id: legal_contract_formation
name: Contract Formation, Breach, and Remedies
description: Offer, acceptance, consideration, interpretation, breach, and the remedies that actually get awarded.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal, IL]
sources: [https://www.law.cornell.edu/wex/contract, https://www.law.cornell.edu/ucc/2]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [contracts, breach, remedies, ucc, formation]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US contract law. It is not legal advice, creates no
> attorney–client relationship, and does not substitute for a licensed attorney.
> Deal documents should be reviewed by counsel before signing.

# Contract Formation, Breach, and Remedies

## Purpose

Cover the full life of a deal document: formation requirements, how courts
read ambiguous terms, what counts as breach, and which remedies courts
actually award. Every seat sale, license, contractor engagement, and
partnership in the operation runs on this doctrine.

## The doctrine

A contract requires offer, acceptance, and consideration (a bargained-for
exchange). Most US contract law is state common law; sales of goods are
governed by UCC Article 2, which modifies several common-law rules.

- **Formation:** the offer must be definite enough to enforce; acceptance
  must mirror the offer (common law mirror-image rule) — UCC § 2-207
  softens this for goods with the "battle of the forms." Consideration
  need not be adequate, but it must exist — past consideration and illusory
  promises generally fail.
- **Statute of Frauds:** certain contracts must be in writing to be
  enforceable — including suretyship, marriage-consideration, one-year
  (not performable within a year), land interests, and UCC goods sales
  of $500+ (§ 2-201). Illinois follows the same categories (740 ILCS 80).
- **Interpretation:** plain meaning first; ambiguity construed against
  the drafter (contra proferentem); course of performance, course of
  dealing, and usage of trade fill gaps (UCC § 2-202, § 1-303).
- **Breach and remedies:** the standard remedy is expectation damages —
  putting the non-breaching party where performance would have (UCC
  §§ 2-711 to 2-715 for buyers/sellers of goods). Consequential damages
  require foreseeability (Hadley v. Baxendale principle). Liquidated
  damages clauses are enforceable if a reasonable forecast of harm, not
  a penalty. Specific performance is reserved for unique goods/property.
- **Defenses:** mistake, misrepresentation/fraud, duress, undue
  influence, unconscionability (UCC § 2-302), impossibility/impracticability,
  frustration of purpose.

## Checklist

1. **Write it down.** Even where oral contracts are enforceable, the
   Statute of Frauds categories and basic evidentiary prudence demand
   writing for anything material.
2. **Name the parties, price, scope, and term precisely.** Most disputes
   are scope disputes — define deliverables, acceptance criteria, and
   what "done" means.
3. **Set the remedy in advance.** Cap liability, choose liquidated
   damages where real forecasting is possible, address consequential-
   damage waivers explicitly (they are enforceable if clear).
4. **Pick governing law and forum.** Illinois vs. counterparty's state;
   arbitration vs. courts (see `legal` ADR coverage in later rings).
5. **Handle the IP.** Assignment vs. license, scope of license, and who
   owns improvements — never leave IP to implication.
6. **Plan the exit.** Termination for convenience/cause, cure periods,
   post-termination duties (confidentiality, IP return, non-solicitation
   within legal bounds).

## Red flags

- Handshake deals for contractor IP — without a written assignment, the
  contractor owns the work (see `legal_copyright_basics`).
- Penalty clauses labeled "liquidated damages" that no forecast supports.
- One-sided limitation-of-liability paired with an uncapped indemnity
  running the other way.
- Auto-renewal and price-escalation clauses nobody calendared.
- "Standard terms" incorporated by hyperlink that nobody read — courts
  enforce them more often than signers expect.

## Authorities

- LII Wex — Contract (formation, breach, remedies overview):
  https://www.law.cornell.edu/wex/contract
- UCC Article 2 (sale of goods): https://www.law.cornell.edu/ucc/2
- UCC § 2-207 (battle of the forms): https://www.law.cornell.edu/ucc/2/2-207
- UCC § 2-715 (consequential damages): https://www.law.cornell.edu/ucc/2/2-715
