---
skill_id: web_sec_dependency_hygiene
name: Dependency Hygiene
description: Keep third-party code from becoming your breach: pinning, auditing, updating, and minimal installation.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web, ops]
version: 1.0.0
---
# Dependency Hygiene
## Purpose
Treat dependencies as part of your attack surface and manage them with the same rigor as your own code.
## Key ideas
- Every dependency is code you ship but did not write; its vulnerabilities become yours.
- Pin versions with lockfiles so builds are reproducible and surprise upgrades cannot sneak in.
- Automated audit tools flag known-vulnerable packages; run them in CI, not once a year.
- Update on a cadence, prioritizing security releases; stale dependencies accumulate known exploits.
- Install minimal dependency sets; each unused package is risk without benefit.

## In practice
Commit lockfiles and make CI fail on known-critical vulnerabilities, with a documented exception process for the rare false positive. Assign dependency updates a regular slot (weekly or biweekly) rather than letting them pile into a dreaded mega-upgrade; small, frequent updates are reviewable and revertable. Vet new dependencies before adopting: maintenance activity, maintainer count, download patterns, and whether a smaller or stdlib alternative exists. Mirror the discipline on the frontend: audit npm packages, prune unused ones, and watch bundle size, because each kilobyte of third-party JavaScript runs with your page's full privileges.

```bash
# Audit on every CI run; fail the build on critical findings
npm audit --audit-level=high
pip-audit --strict

# Keep the tree lean: find what nothing uses
npx depcheck
pip list --not-required

# Upgrade deliberately, then run the full test suite
npm update && npm test
```

## Common mistakes
- Shipping without lockfiles, so builds silently pick up new, unreviewed versions.
- Ignoring audit findings for months until a known CVE becomes the breach vector.
- Adding dependencies casually and never removing the ones the feature outgrew.

## Checklist
- Are lockfiles committed with CI failing on critical audit findings?
- Is there a regular, small-batch update cadence?
- Are unused dependencies pruned on a schedule?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
