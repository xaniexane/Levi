---
skill_id: ml_levi_honest_limits
name: LEVI Brain: Honest Limits Doctrine
description: What the tiny brain can and cannot do, per docs/BRAIN_TRAINING.md section 3 - the anti-hype contract.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI Brain: Honest Limits Doctrine

## Purpose

State the honest-limits doctrine from docs/BRAIN_TRAINING.md plainly:
the tiny brain is proof that the learning loop works, not a capable
mind - and define exactly what evidence would change that assessment.

## When to use

- Any claim about what LEVI's brain can do.
- Reviewing sample generations (set expectations first).
- Deciding whether the brain is ready for a bigger role.

## Core ideas

What the tiny brain **can** do (verified):

- Demonstrate the full pipeline works end to end on LEVI's own data.
- Serve as a smoke test for corpus quality: if loss doesn't move,
  the corpus is broken.
- Run as the `levi-brain` provider - LEVI's own native brain inside
  the agent runtime, selected explicitly.

What it **can't** do: reliably answer questions, hold a long
conversation, or emit tool calls. It learns spelling, local phrasing,
and topic texture - not reasoning, math, code, or reliable facts.
Sample generations are fluent-ish gibberish with corpus flavor; that
is *expected*, and the meaningful signals are loss decreasing and
held-out loss tracking train loss.

The doctrine's rule: never claim "formally proven" or "capable"
beyond what the artifacts show. The artifacts are train_log.json
(loss fell), eval.json (held-out tracked), samples.md (texture, not
brilliance).

## Gotchas

- Enthusiasm is the enemy here: a falling loss curve feels like
  intelligence arriving. It isn't - it's the loop working.
- The doctrine protects the project: honest limits today are what
  make bigger claims credible later.
- In the agent loop the deterministic rule-based `local` planner
  remains default; levi-brain answers in prose when explicitly
  selected.

## Quick reference

- Proof of learning, not a capable mind. Evidence: loss down,
  held-out tracking, samples textured. Hype: forbidden.
