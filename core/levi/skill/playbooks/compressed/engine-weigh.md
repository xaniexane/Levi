---
skill_id: compressed.engine-weigh
name: Weigh Pattern
description: Judge a proposition with weighted evidence for and against, a named lean, and calibrated confidence.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, judgment, evidence, confidence]
version: 1.0.0
---
# Weigh Pattern

## Purpose

The weighing mind's discipline: hold a proposition, lay evidence on
both pans, and read the lean — for, against, or balanced — with the
decisive factors named. Weights are evidence strengths, not votes: one
strong reason outweighs three weak ones, and the trace says which.

## When to use

- "Should we build this?" — evidence both ways, need a lean.
- Retrospectives: did the call we made actually weigh right?
- Any yes/no judgment where the reasoning must be auditable later.
- Run it through the `weigh` engine (`levi engines run weigh`).

## The pattern

1. **State the proposition in one sentence.** If you can't, the
   evidence will scatter — the engine refuses empty propositions.
2. **List points for and against, each with a weight.** Default 1.0;
   use weight to say "this reason matters more", not to stuff the ballot.
3. **Set the threshold.** Margins inside ±threshold read as *balanced* —
   an honest "too close to call" instead of a false lean.
4. **Read the decisive factors.** The top-weighted points on each side
   are the whole argument; everything else is commentary.

## Honest limits

- Confidence calibrates to the margin: coin flips score ~0.5, runaways
  climb toward 1.0. It never reports certainty it didn't earn.
- No evidence on either side → balanced, confidence 0.5. The engine
  judges; the keeper decides.
- Weighing is inward work: it judges what's in front of it, never goes
  scouting for new evidence. Sensing is a different engine's job.
