---
skill_id: ml_train_val_test_splits
name: Train/Validation/Test Splits
description: Why three splits exist, what each may be used for, and how leakage between them invalidates everything.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training, evaluation]
version: 1.0.0
---
# Train/Validation/Test Splits

## Purpose

Define the three-way split discipline: train fits, validation steers
decisions, test judges once - and explain why peeking at test during
development voids the measurement.

## When to use

- Setting up any ML experiment.
- Reviewing someone else's reported numbers.
- Carving held-out data from a corpus (cf. carve_heldout.py).

## Core ideas

- **Train:** gradient updates happen here. The model may memorize it
  freely.
- **Validation:** used for *decisions* - early stopping, hyperparameter
  choice, checkpoint selection. The model never trains on it, but you
  are allowed to look many times; accept that repeated tuning
  overfits validation slightly.
- **Test:** locked away, evaluated rarely (ideally once, at the end).
  This is the honest estimate of generalization. Every decision made
  using test numbers leaks into the model and inflates the score.

Typical ratios: 80/10/10 or 90/5/5 at scale (held-out sets need only
be large enough for low-variance estimates - a few thousand examples
usually suffices). For language modeling, held-out *documents* (not
random chunks) better measure generalization; LEVI's dialogue pipeline carves a
deterministic, seed-fixed, stratified held-out set (carve_heldout.py)
for exactly this reason.

## Gotchas

- Near-duplicates across splits (common in web text) silently inflate
  scores - dedup *across* splits, not just within train.
- Time-series data must split by time, not randomly - random splits
  let the future leak into training.
- "Test set" reused across 50 experiments is a validation set with a
  fancy name. Rotate or accept the optimism.

## Quick reference

- Train: fit. Val: decide (early stop, tune). Test: judge once.
  Dedup across splits; split time-series by time.
