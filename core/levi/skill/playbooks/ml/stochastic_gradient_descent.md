---
skill_id: ml_stochastic_gradient_descent
name: Stochastic Gradient Descent and Minibatches
description: Why we train on minibatches, how batch size changes the noise/throughput tradeoff, and shuffling discipline.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Stochastic Gradient Descent and Minibatches

## Purpose

Explain minibatch SGD: estimate the gradient on a random subset,
update, repeat - and how batch size trades gradient noise against
hardware throughput.

## When to use

- Choosing batch size for a training run.
- Understanding the linear scaling rule for learning rates.
- Debugging training instability that tracks batch composition.

## Core ideas

Each step samples B examples, averages their gradients, updates.
B=1 is pure SGD (maximum noise), B=N is full batch (no noise, no
speed). Practical B sits where hardware saturates: 32-512 sequences
for small LMs, larger with accumulation.

Two effects of larger B: (1) less gradient noise - smoother steps,
can take larger lr (the linear scaling rule: double B, double lr, up
to limits); (2) fewer updates per epoch - less of SGD's implicit
regularization, sometimes worse generalization ("generalization gap"
of large batches). Small batches generalize slightly better but train
slower per step.

**Shuffle every epoch.** Without shuffling, the model sees data in a
fixed order and the gradient estimates correlate - worst case, it
oscillates between modes of the data instead of descending.

## Gotchas

- Batch size interacts with BatchNorm statistics (not an issue for
  LayerNorm/RMSNorm transformers).
- "Batch size" for LMs usually means *tokens* per step, not sequences
  - report tokens for comparability.
- Gradient accumulation simulates large B with small memory: N micro-
  steps, sum gradients, one update. Slightly different numerics, same
  idea.

## Quick reference

- Bigger batch: less noise, more throughput, needs higher lr, mildly
  worse generalization. Always shuffle; count batch size in tokens.
