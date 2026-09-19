---
skill_id: compressed.deterministic-verdict
name: Deterministic Verdict Law
description: Same inputs → same verdict, every time. The law that makes engines auditable, replayable, and trustworthy.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, determinism, audit, law]
version: 1.0.0
---
# Deterministic Verdict Law

## Purpose

The standing law every engine obeys: **same inputs → same verdict,
every time.** It is what separates an engine from an opinion. When a
verdict can be replayed byte-for-byte, it can be audited, disputed,
and trusted.

## When to use

Always. This is not a pattern you opt into — it's the floor under all
of them. Invoke it whenever a verdict's reproducibility is questioned.

## The law

1. **No hidden inputs.** Everything the verdict depends on arrives in
   the input dict. Wall-clock time, random seeds, ambient state —
   either passed explicitly or not used.
2. **Ties break in the open.** Any nondeterminism (a tie, an unordered
   set) resolves by a stated rule — option id, insertion order, a
   named coin — and the trace says which rule fired.
3. **Purity is enforced.** Engines compute. No network, no filesystem,
   no messages, no money. If it has a side effect, it's not an engine.
4. **Replay is the test.** Feed yesterday's inputs; expect yesterday's
   verdict. Any drift is a bug, reported as one.

## Honest limits

- Determinism is about the *machine*, not the *world*. The inputs can
  be uncertain (a weight you guessed); the machine's handling of them
  is exact.
- A deterministic wrong answer is still wrong — the law makes errors
  *findable*, not impossible. That's the whole point: findable errors
  get fixed; vibes don't.
