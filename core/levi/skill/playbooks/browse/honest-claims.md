---
skill_id: browse.honest_claims
name: Honest Claims Only
description: No blanket secure/private/anonymous — every claim is per-mechanism and graded OBSERVED, INFERRED, or UNVERIFIED.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, honesty, claims, grading]
version: 1.0.0
---

# Honest Claims Only

Saying less than we can prove is the feature. No module, docstring,
UI string, or receipt may claim "secure", "private", or "anonymous"
as a blanket. Allowed claims are per-mechanism and graded.

## The three grades

- **OBSERVED** — a named direct observation exists. State what was
  observed and how: "tracker list v2026-09-29 applied; 14 of 17
  requests matched." The observation is named, dated, countable.
- **INFERRED** — a named heuristic ran. The "signal, not verdict"
  caveat renders structurally, never as a footnote: "page shows no
  third-party requests (static parse; dynamic requests not observed)."
  The limit of the inference is part of the claim.
- **UNVERIFIED** — the deny-closed default. "Tor routing", "on-device
  ML translation", anything not wired or not yet audited. UNVERIFIED
  is not shameful; it is accurate. A whole-layer "secure browsing"
  label stays UNVERIFIED until a real audit exists.

## Rules

1. Grades never self-upgrade. An INFERRED claim does not become
   OBSERVED because it was right twice. Re-grading needs new evidence,
   named.
2. Every grade names what evidence would change it. "This becomes
   OBSERVED when the on-device run completes with a logged digest."
3. The grade travels with the claim — in the API return, the receipt,
   and the surface. A grade stripped at the UI boundary is a lie by
   omission.
4. Refused patterns, concretely: "military-grade", "100% private",
   "anonymous browsing", "unbreakable", "zero-knowledge" (unless the
   mechanism is actually proven zero-knowledge, which ours are not
   until audited). Marketing adjectives are claims; claims need
   grades.

## The lineage

This is X-Posed's one honest pattern, structuralized: probabilistic
claims labeled as probabilistic, in the product itself. And it is the
answer to Omni's "100% on-device ML" — a claim the user cannot audit
is marketing until audited. We do not ship marketing.

## The crown jewels (law 11)

The credential broker is the highest-value target in the layer, so it
gets the strictest discipline in this playbook:

- No blanket claim on the broker, ever: no "secure password
  manager", no "military-grade", no "unbreakable", no
  "zero-knowledge". Per-mechanism graded claims only, and the broker
  as a whole stays UNVERIFIED until a real audit exists and names it.
- Each mechanism names its grade and its evidence: generation is
  OBSERVED (stdlib `secrets` CSPRNG via
  `cybrus/vault.py::generate_password`, min length 12); storage
  encryption is INFERRED-until-the-binding-is-tested
  (veil-sealed, keeper-held keys); the whole-store claim is
  UNVERIFIED until audited.
- The grade travels with the claim — in the API return, the receipt,
  and the surface. A credential receipt that drops its grade is a
  lie by omission about the crown jewels.

## The check

Grep the diff for secure, private, anonymous, military, unbreakable,
zero-knowledge. Every hit must be a graded per-mechanism claim or it
does not ship.
