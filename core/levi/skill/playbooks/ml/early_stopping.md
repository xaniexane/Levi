---
skill_id: ml_early_stopping
name: Early Stopping
description: Halting training when held-out loss stops improving: patience, checkpoint discipline, and what it regularizes.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Early Stopping

## Purpose

Explain early stopping as both a compute saver and a regularizer:
monitor held-out loss, keep the best checkpoint, stop when it stops
improving - with the patience and bookkeeping done right.

## When to use

- Any training run with a validation set.
- Small-data regimes where overfitting arrives fast.
- Deciding "is this run done or just slow?"

## Core ideas

Track validation loss every K steps. Keep the checkpoint with the
lowest val loss seen. If no improvement for `patience` evaluations,
stop and *restore the best checkpoint* - the final weights are not the
best weights. Typical patience: 3-10 evaluations depending on eval
noise.

Why it regularizes: training time is a capacity knob. Early in
training the model fits broad patterns; late, it fits noise. Stopping
at the val minimum is like choosing the model complexity that
generalizes best - a free regularizer that costs nothing but the
discipline to keep the best checkpoint.

At LLM pre-training scale, early stopping is rarely used (compute-
optimal plans train once through the data - one epoch, no U-turn to
catch). It shines in fine-tuning and small-model regimes.

## Gotchas

- Val loss is noisy - smooth it or require improvement beyond a
  min_delta, or you stop on noise.
- Restoring the best checkpoint is the step everyone forgets. The
  stopped-at weights are worse by construction.
- Early stopping on a *contaminated* val set stops at the wrong place
  - dedup val against train first.

## Quick reference

- Monitor val loss, keep best checkpoint, stop after `patience`
  stagnant evals, restore best. Free regularization for small runs.
