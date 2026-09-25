---
skill_id: compressed.engine-plumbline
name: Plumbline Pattern
description: Hang declared laws against any verdict and prove which held, which broke, and the exact evidence — laws first, proof after, absence never satisfies a claim.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, invariants, verification, law-guard-prove, proof]
version: 1.0.0
---
# Plumbline Pattern

## Purpose

Turn "trust me, the invariants hold" into a machine-checked receipt. You
declare the laws up front — each a small declarative rule, data never
code — and the plumbline hangs every law against the verdict and reports
held vs broken with the observed value beside the claim. A plumb line
does not argue; it shows true.

This is Chauncey's law-guard-prove rule as a reusable pattern: laws
first (invariants declared in plain words), implementation second, proof
before the commit.

## When to use

- After any engine verdict: hang its declared laws against the result
  before you trust it.
- Before a commit: the proof gate — the declared invariants of the
  change, checked against the actual outputs.
- After a pipeline stage: snapshot in, laws out, broken laws named.
- Whenever someone claims "nothing changed": the plumbline shows what
  the verdict actually says.

## The law shape

Each law is a dict — no code, no eval, no exec:

```json
{"id": "partition",
 "claim": "every item lands in exactly one group",
 "path": "duplicate_count", "op": ">=", "value": 0}
```

- `id`: unique, non-empty. `claim`: the plain-words invariant.
- `path`: dot-path into the verdict — dict keys, integer indices for
  lists (`groups.0.canonical`). Max 16 segments.
- `op`: one of `exists | missing | == | != | < | <= | > | >= |
  in | not-in | contains | len== | len>= | len<=`.
- `value`: required for every op except `exists`/`missing`; must be a
  list for `in`/`not-in`, a scalar for `contains`, an int >= 0 for the
  `len*` ops.

## The absence rule

Absence never satisfies a positive claim. A comparison op against a
missing path is a FAIL — the verdict did not uphold the law — recorded
as `observed: "<missing>"`. Only the `missing` op holds on absence.
A missing path never quietly becomes true, zero, or empty.

## Reading the verdict

`status` is `held` or `broken`; `held_count`/`broken_count` over
`law_count`; `confidence` is the held fraction. Every law entry carries
`held`, the `observed` value, and an `evidence` note — a bare
pass/fail is refused by design.

## Laws of this pattern

1. Declare at least one law — a plumb line with no wall proves nothing.
2. Same inputs → byte-identical verdict (sans timestamp).
3. Malformed laws (unknown op, bad path, wrong value shape, duplicate
   ids) are refused with a named error, never coerced.
4. The DSL never executes code; paths are lookups, ops are fixed.
5. Nothing here acts, sends, or spends — it only proves.
