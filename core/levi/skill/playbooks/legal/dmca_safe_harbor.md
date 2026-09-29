---
skill_id: legal_dmca_safe_harbor
name: DMCA Safe Harbors and Takedown Practice
description: Section 512 safe harbors for platforms, the notice-and-takedown workflow, counternotices, and §1201 anti-circumvention basics.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal]
sources: [https://www.law.cornell.edu/uscode/text/17/512, https://www.copyright.gov/dmca/, https://www.law.cornell.edu/uscode/text/17/1201]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [copyright, dmca, platform, takedown, safe-harbor]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal copyright law. It is not legal advice, creates no
> attorney–client relationship, and does not substitute for a licensed attorney.
> Takedown and counternotice decisions carry perjury-adjacent risk; get counsel
> involved in the workflow design.

# DMCA Safe Harbors and Takedown Practice

## Purpose

Show a platform operator how the § 512 safe harbors work and how to run a
compliant notice-and-takedown operation: designated agent, notice intake,
expeditious removal, counternotice and putback, repeat-infringer policy.
Also covers § 1201 anti-circumvention basics and the triennial exemptions.

## The doctrine

Section 512 offers service providers safe harbors against money damages
for user infringement in four functions: transitory communications
(§ 512(a)), system caching (§ 512(b)), storage at user direction
(§ 512(c) — the workhorse for UGC platforms), and information-location
tools (§ 512(d)). The § 512(c) harbor requires, among other things: no
actual or "red flag" knowledge of infringement, no direct financial
benefit combined with control, expeditious removal on compliant notice,
a designated agent registered with the Copyright Office, and a
repeat-infringer termination policy.

- **Notice-and-takedown (§ 512(c)(3)):** a compliant notice identifies the
  work, the infringing material, and includes a good-faith statement and
  signature under penalty of perjury. Noncompliant notices don't trigger
  the removal duty — but ignoring plausible notices risks "red flag"
  knowledge findings.
- **Counternotice and putback (§ 512(g)):** the user may counternotice;
  the provider must restore the material in 10–14 business days unless
  the complainant files suit. Misuse of takedown (knowing material
  misrepresentation, § 512(f)) creates liability for the sender.
- **Designated agent:** must be registered with the Copyright Office's
  online directory (copyright.gov/dmca-directory/) — a lapsed
  registration can cost the harbor.
- **§ 1201 anti-circumvention:** bans circumventing technological measures
  controlling access to copyrighted works, and trafficking in circumvention
  tools. It is independent of infringement — you can violate § 1201
  without infringing. Triennial rulemakings grant narrow exemptions
  (security research, repair, accessibility, etc.).
- **Standard technical measures (§ 512(i)):** the harbor requires
  accommodating them; the repeat-infringer policy must be reasonably
  implemented.

## Checklist

1. **Register and maintain the designated agent** with the Copyright
   Office; re-verify the directory listing annually.
2. **Publish a copyright policy** with a working notice intake address and
   the counternotice procedure.
3. **Build the intake workflow:** notice validity check (§ 512(c)(3)
   elements) → expeditious removal/disablement → user notification →
   counternotice window → putback at 10–14 business days absent suit.
4. **Implement and document a repeat-infringer policy** — written,
   communicated to users, and actually enforced; keep termination logs.
5. **Train for § 512(f) risk:** staff must understand that knowingly
   false takedowns create sender liability; build a review step for
   edge cases (fair-use-adjacent content, see `legal_fair_use`).
6. **For § 1201:** never ship circumvention tooling; check the current
   triennial exemptions before relying on one (security research,
   unlocking, repair exemptions are narrow and conditional).

## Red flags

- No designated agent registration, or a registration that lapsed years ago.
- "Takedown on any complaint, no review" — invites § 512(f) exposure and
  user revolt; "never takedown" forfeits the harbor.
- A repeat-infringer policy that exists on paper and is never enforced.
- Ignoring counternotices or restoring material instantly without the
  statutory waiting period.
- Assuming the safe harbor covers the provider's *own* infringing acts —
  it covers user infringement, not yours.

## Authorities

- 17 U.S.C. § 512: https://www.law.cornell.edu/uscode/text/17/512
- 17 U.S.C. § 1201: https://www.law.cornell.edu/uscode/text/17/1201
- Copyright Office DMCA designated-agent directory:
  https://www.copyright.gov/dmca-directory/
- Copyright Office § 1201 rulemaking page: https://www.copyright.gov/1201/
