---
skill_id: legal_open_source_license_choice
name: Open-Source License Choice and Compatibility
description: Choosing between MIT, Apache-2.0, BSD, and GPL-family licenses, and how licenses combine in one project.
category: legal
risk: info
permissions: []
requires_confirmation: false
jurisdiction: [US-federal]
sources: [https://opensource.org/licenses, https://www.apache.org/licenses/LICENSE-2.0, https://www.law.cornell.edu/uscode/text/17/204]
requires_attorney_review: false
disclaimer_version: 1.0
last_verified: 2026-09-28
tags: [software, licensing, open-source, mit, apache, bsd]
version: 1.0.0
---

> **General legal information — not legal advice.** This playbook is educational
> material about US software licensing practice. It is not legal advice, creates
> no attorney–client relationship, and does not substitute for a licensed
> attorney.

# Open-Source License Choice and Compatibility

## Purpose

Help a builder pick the right license for original code and combine
third-party licenses without creating conflicts. Covers the permissive
family (MIT, BSD, Apache-2.0), the copyleft family (GPL, LGPL, AGPL), and
the compatibility rules that govern mixed-license projects.

## The doctrine

A license choice is a copyright decision: as the author you hold the
exclusive rights (17 U.S.C. § 106), and a transfer of copyright ownership
— as opposed to a nonexclusive license — must be in a signed writing
(17 U.S.C. § 204(a)). Open-source licenses are nonexclusive permissions
with conditions; violating a condition can terminate the permission and
expose the user to infringement claims.

- **MIT / BSD (2- and 3-clause):** permissive, attribution-only. Code can
  be incorporated into proprietary products. No patent grant is express
  (BSD/MIT) — a practical gap Apache-2.0 closes.
- **Apache-2.0:** permissive plus an express patent grant (§3) and a
  patent-retaliation clause (§3: suing over the work's patents terminates
  your license). Includes NOTICE-file attribution mechanics.
- **GPL family:** copyleft — derivative works distributed must carry the
  same license (see `legal_gpl_copyleft_scope`).
- **Compatibility direction:** permissive code can generally go *into*
  GPL projects (the combined work is GPL); GPL code cannot go into
  permissive-licensed projects without the result becoming GPL. Apache-2.0
  is compatible with GPLv3 but *not* with GPLv2 (patent-termination
  language conflict) — a classic trap.
- **Dual licensing** (e.g., GPL + commercial) is a business model, not a
  loophole: users pick one track, and the GPL track's conditions still
  apply to those who choose it.

## Checklist

1. **Decide the goal first.** Maximum adoption and proprietary reuse →
   permissive (Apache-2.0 is the default recommendation: patent grant
   included). Forcing derivatives open → copyleft (GPLv3 or AGPLv3 if
   network use matters).
2. **Put the license text in the repo root** (LICENSE file) and add
   SPDX-License-Identifier headers to source files.
3. **Get contributor rights straight.** Contributors keep their copyright
   unless they assign it; a Contributor License Agreement (CLA) or
   Developer Certificate of Origin (DCO) records the inbound grant.
   Without one, the project's right to relicense is fragile.
4. **Check compatibility before adding a dependency.** Map every
   dependency's license against the project's license; flag Apache-2.0
   into GPLv2-only, and any GPL-family code into permissive projects.
5. **Mind the NOTICE and attribution duties.** Apache-2.0 NOTICE files,
   BSD advertising-clause history (original 4-clause BSD), and MIT
   copyright notices must survive redistribution.

## Red flags

- No LICENSE file at all — default is "all rights reserved," not
  open source, regardless of what the README implies.
- "It's on GitHub so it's open source" — public visibility is not a
  license grant.
- Mixing GPLv2-only code with Apache-2.0 dependencies.
- Contributors who never signed a CLA/DCO in a project that may
  relicense commercially later.
- Snippets copied from Q&A sites into commercial code without checking
  the site's content license.

## Authorities

- OSI approved license list: https://opensource.org/licenses
- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0
- 17 U.S.C. § 204 (transfers in writing):
  https://www.law.cornell.edu/uscode/text/17/204
- FSF license compatibility list:
  https://www.gnu.org/licenses/license-list.html
