---
skill_id: legal_gpl_copyleft_scope
name: GPL Copyleft Scope and Compliance
description: When GPL copyleft reaches your code, what counts as a derivative work, and how to run a compliance audit.
category: legal
risk: moderate
permissions: []
requires_confirmation: false
jurisdiction: [US-federal]
sources: [https://www.law.cornell.edu/uscode/text/17/106, https://www.gnu.org/licenses/gpl-3.0.html, https://www.copyright.gov/comp3/]
requires_attorney_review: true
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [software, licensing, gpl, copyleft, compliance]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US federal copyright law. It is not legal advice, creates no
> attorney–client relationship, and does not substitute for a licensed attorney.
> License-compliance decisions with real exposure require attorney review.

# GPL Copyleft Scope and Compliance

## Purpose

Give a builder a repeatable way to answer the question that matters most in
open-source compliance: *does the GPL reach this code, and if so, what must we
do?* Covers GPLv2/GPLv3 copyleft mechanics, the derivative-work trigger,
common boundary questions (linking, plugins, SaaS), and a compliance-audit
checklist. This is the playbook for the Alloy/Metrolist GPL moment: copyleft
is live risk the day GPL code enters the tree.

## The doctrine

Copyright gives the licensor the exclusive rights of reproduction, derivative
works, distribution, and public display/performance (17 U.S.C. § 106). The GPL
is a copyright license: it *permits* those acts only on its conditions. The
core copyleft condition (GPLv2 §2(b), GPLv3 §5(c)): when you convey a work
"based on the Program" — a derivative work under copyright law — you must
license the entire work under the GPL and provide corresponding source.

Key boundaries, stated as general principles (fact-specific; counsel decides
the close calls):

- **Derivative work is the trigger.** Mere aggregation on the same medium
  (GPLv2 §2, GPLv3 §5: "mere aggregation") is not enough to pull separate
  works under copyleft. What counts as derivative is a copyright question,
  not a license-defined one — courts look at creative interdependence.
- **Static vs. dynamic linking** is debated, not settled law. The FSF's
  position is that both create derivatives; no US court has squarely held
  that dynamic linking alone creates a derivative work. Treat FSF guidance
  as the conservative compliance posture, not as decided law.
- **GPLv2 has no SaaS trigger.** Running modified GPLv2 code as a network
  service, without distribution, does not trigger source obligations under
  GPLv2. The AGPL exists precisely to close that gap — AGPLv1/v3 §13
  triggers on network interaction.
- **GPLv3 adds explicit patent and anti-tivoization terms** (§§10–11 patent
  grant; §6 installation information). Upgrading license versions changes
  obligations — "GPLv2 or later" and "GPLv3 only" are different licenses.
- **LGPL is the library exception.** LGPLv2.1/LGPLv3 permit linking from
  proprietary applications under stated conditions (reverse-engineering
  allowance, relinking rights) — check the version's exact terms.

## Checklist

1. **Inventory.** List every third-party component in the tree with its
   exact license and version (SPDX identifiers in a bill of materials).
2. **Classify.** For each GPL-family component: which GPL version, "or
   later" or not, and how it is integrated (linked, forked, plugin,
   separate process, network service).
3. **Apply the trigger test.** Was the GPL work modified, linked into, or
   otherwise formed into a derivative? If conveyed (distributed) — not
   merely run internally — copyleft conditions attach.
4. **Check the obligations.** Corresponding source availability, license
   notices preserved, GPL copy included, no additional restrictions
   (GPLv3 §10).
5. **Remediate or relicense.** Options: comply (publish source), replace
   the component, re-architect the boundary (separate process/IPC is
   stronger separation than in-process linking, though not a legal
   guarantee), or negotiate a commercial license from the copyright holder.
6. **Prevent recurrence.** License-scanning in CI (e.g., scancode-class
   tooling), a component-approval gate before new dependencies land, and a
   written open-source policy naming who may approve GPL-family intake.

## Red flags

- "We'll just use the GPL library internally" — then shipping it in an
  APK, installer, or container image *is* distribution.
- Vendored GPL code with the license headers stripped.
- A dependency that is "GPLv2 or later" being treated as "GPLv2 only"
  (or vice versa) — the upgrade path changes patent and tivoization terms.
- Dual-licensed components where the commercial terms were never actually
  purchased — the GPL terms are the ones that apply.
- AI-generated code trained on GPL sources: unsettled law, flag for
  counsel, do not assume it is clean.

## Authorities

- 17 U.S.C. § 106 — exclusive rights in copyrighted works:
  https://www.law.cornell.edu/uscode/text/17/106
- GNU GPLv3 full text: https://www.gnu.org/licenses/gpl-3.0.html
- GNU AGPLv3 §13 (network interaction):
  https://www.gnu.org/licenses/agpl-3.0.html
- U.S. Copyright Office Compendium (derivative-work authorship rules):
  https://www.copyright.gov/comp3/
