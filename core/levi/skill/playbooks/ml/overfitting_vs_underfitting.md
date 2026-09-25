---
skill_id: ml_overfitting_vs_underfitting
name: Overfitting vs Underfitting
description: Reading the train/held-out loss gap: what each failure looks like and the correct response to each.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Overfitting vs Underfitting

## Purpose

Teach the central diagnostic of machine learning: compare training
loss to held-out loss, identify which regime you are in, and apply
the right fix (more capacity vs more regularization - never the
wrong one).

## When to use

- Any training run, at every checkpoint review.
- Deciding whether to grow the model or regularize it.
- Explaining ML debugging to a newcomer.

## Core ideas

- **Underfitting:** train loss itself is high. The model cannot even
  memorize the training data. Fix: more capacity (bigger model, longer
  training, higher lr), better features/data, less regularization.
- **Overfitting:** train loss low, held-out loss high (or rising).
  The model memorized training specifics that don't generalize. Fix:
  more data, regularization (dropout, weight decay, augmentation),
  early stopping, *smaller* model.
- **Good fit:** both low and tracking each other. (For LLMs, mild
  overfitting to the training distribution is normal - the goal is
  downstream capability, and train/held-out gaps are expected at
  scale.)

The learning-curve shapes: underfitting = both curves plateau high;
overfitting = train keeps falling while held-out U-turns upward. The
U-turn point is where early stopping would have fired.

## Gotchas

- "More data" fixes overfitting only if the new data is from the
  right distribution - more of the same bias doesn't help.
- Regularizing an underfit model makes it worse. Diagnose first,
  prescribe second.
- At LLM scale the bias-variance framing gets murky (double descent),
  but the train-vs-held-out read stays the primary instrument.

## Quick reference

- Train high -> underfit -> add capacity/training. Gap wide ->
  overfit -> add data/regularization. Diagnose before prescribing.
