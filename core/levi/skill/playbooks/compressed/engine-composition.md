---
skill_id: compressed.engine-composition
name: Engine Composition
description: Compose small deterministic engines into pipelines — one engine's verdict feeds the next engine's input.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, composition, pipelines, architecture]
version: 1.0.0
---
# Engine Composition

## Purpose

One engine answers one question well. Hard questions need several:
triage the options, weigh the winner's risks, check the cadence of
delivery. Composition chains engines so the verdict of one becomes
the input of the next — the capability graph's smallest honest unit.

## When to use

- A decision that needs ranking *and* risk-judgment *and* timing.
- Building a new capability out of primitives instead of one big
  bespoke machine (the graph grows by composition, not by authorship).
- Auditing a complex call: each engine's trace is a link in the chain.

## The pattern

1. **Keep engines small.** One question per engine. If an engine needs
   two verdicts, it's two engines.
2. **Verdict → input.** Map fields explicitly: triage's `winner` feeds
   weigh's `proposition`; cadence's `next_due` feeds a scheduler's
   `at` field. No implicit coupling.
3. **Trace the chain.** Keep every engine's trace in order. A composed
   pipeline's audit is the concatenation of its links' traces.
4. **Fail at the first broken link.** A malformed input to engine two
   is a hard refusal — never coerce a verdict into the shape you wish
   it had.

## Honest limits

- Composition multiplies questions, not answers: garbage in at link
  one is garbage out at link three, just more traceably.
- Keep the chain short. Three engines deep is legible; seven is a
  Rube Goldberg machine with a confidence score.
- Engines compute; they never act. A composed pipeline still ends at
  a verdict — action stays behind the six gates.
