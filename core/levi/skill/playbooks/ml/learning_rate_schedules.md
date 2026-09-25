---
skill_id: ml_learning_rate_schedules
name: Learning Rate Schedules: Warmup, Decay, Cosine
description: Why the learning rate should change during training, and the warmup-then-cosine recipe that trains transformers.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Learning Rate Schedules: Warmup, Decay, Cosine

## Purpose

Explain why a fixed learning rate is leaving performance on the
table: start small (warmup), train high, decay to settle - and give
the cosine schedule as the default recipe.

## When to use

- Setting up any training run longer than a toy.
- Debugging early divergence (usually missing warmup).
- Understanding what --steps and decay horizons mean in configs.

## Core ideas

**Warmup** (first few % of steps, linear ramp 0 -> max lr): at init,
weights are random and gradients are wild; a full lr step can
catapult the model into a bad region it never recovers from.
Warmup walks it out gently. Skipping warmup is the most common cause
of "loss explodes in the first 500 steps".

**Decay:** late in training, large steps bounce around the minimum;
shrinking lr lets the model settle. **Cosine decay** - lr follows a
half-cosine from max to min over the run - is the modern default: it
spends a long time at moderate lr (exploration) then decays smoothly
(fine settling). Linear decay works but wastes the middle.

LEVI's tiny-gpt-v2: cosine from 3.0e-4 to 3.0e-5 over 5400 steps with
100 warmup steps - textbook recipe at small scale.

## Gotchas

- The schedule's horizon must match the run length: cosine to step
  5400 then continuing to 8000 re-raises... no - cosine stays at min,
  but you lose the settling benefit for the extra steps. Set the
  horizon to the actual planned steps.
- Warmup too long wastes compute; 1-5% of steps is plenty.
- Step decay (divide by 10 at fixed points) still appears in CNN
  recipes but is strictly worse-behaved than cosine for LMs.

## Quick reference

- Warmup 1-5% linear, then cosine max->min over the run. Match the
  horizon to actual steps. No warmup -> early divergence risk.
