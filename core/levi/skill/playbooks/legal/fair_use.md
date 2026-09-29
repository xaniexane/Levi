---
skill_id: legal_fair_use
name: Fair Use — The Four Factors in Practice
description: How courts weigh the four fair-use factors, with attention to AI training-data disputes and platform content.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal]
sources: [https://www.law.cornell.edu/uscode/text/17/107, https://www.copyright.gov/fair-use/]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [copyright, fair-use, ai-training, transformative]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal copyright law. It is not legal advice, creates no
> attorney–client relationship, and does not substitute for a licensed attorney.
> Fair use is intensely fact-specific; close calls require attorney review.

# Fair Use — The Four Factors in Practice

## Purpose

Give a working understanding of 17 U.S.C. § 107's four-factor test so a
builder can spot fair-use issues early — in platform content moderation,
training-data decisions, and product features that reuse others' works.
This playbook explains the framework; it does not bless any particular use
as fair.

## The doctrine

Fair use is a case-by-case defense, not a right granted in advance. Courts
weigh four non-exclusive factors (§ 107):

1. **Purpose and character of the use** — including whether it is
   commercial and whether it is *transformative* (adds new expression,
   meaning, or message). Since *Campbell v. Acuff-Rose Music*, 510 U.S.
   569 (1994), transformativeness has been the factor courts weigh most
   heavily. Parody, criticism, and commentary are the classic favored
   purposes.
2. **Nature of the copyrighted work** — creative works get thicker
   protection than factual ones; unpublished status historically weighed
   against fair use.
3. **Amount and substantiality** — how much was taken, qualitatively as
   well as quantitatively. Taking "the heart of the work" can defeat fair
   use even at small quantities.
4. **Effect on the market** — harm to the actual or *potential* market
   for the original, including markets the copyright holder would
   reasonably develop. Courts increasingly ask about licensing markets.

- **No bright lines.** There is no "30 seconds," "10%," or "five-word"
  rule in the statute — those are myths.
- **AI training data is contested ground.** Whether training machine-
  learning models on copyrighted works is fair use is actively being
  litigated; courts have split on adjacent questions and no Supreme Court
  holding settles model training. Treat any training-data fair-use claim
  as an open legal question requiring counsel, not a settled defense.
- **Commerciality is not dispositive** but it counts: a commercial
  transformative use can still be fair (*Campbell* itself was commercial
  parody), while a noncommercial verbatim copy can still infringe.

## Checklist

1. **Identify the use precisely.** What work, how much, transformed how,
   commercial or not, whose market is affected.
2. **Walk all four factors in writing.** A contemporaneous fair-use memo
   (even an internal one) shows good-faith analysis; its absence looks
   like indifference.
3. **Weigh transformativeness honestly.** Repackaging the same expression
   for the same audience is the weakest position.
4. **Check the market factor twice.** Ask not only "does this replace
   sales" but "is there a licensing market we are bypassing."
5. **For platform features:** pair the analysis with DMCA safe-harbor
   posture (see `legal_dmca_safe_harbor`) — fair use and safe harbors are
   different defenses solving different problems.
6. **Escalate the close ones.** Training-data ingestion, dataset
   distribution, and model outputs that reproduce expressive text go to
   counsel before launch, not after a letter arrives.

## Red flags

- "It's only X seconds/percent" stated as if the statute contained a
  threshold — it does not.
- Relying on fair use for verbatim reproduction at scale (datasets,
  mirrors, scraped libraries).
- Assuming noncommercial = fair, or educational = automatically fair.
- Model outputs that memorize and emit long expressive passages from
  training works.
- No written analysis anywhere — fair use argued for the first time in a
  demand-letter response.

## Authorities

- 17 U.S.C. § 107: https://www.law.cornell.edu/uscode/text/17/107
- *Campbell v. Acuff-Rose Music*, 510 U.S. 569 (1994) (transformativeness):
  https://www.law.cornell.edu/supremecourt/text/510/569
- Copyright Office fair-use index: https://www.copyright.gov/fair-use/
