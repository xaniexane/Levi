---
skill_id: ml_regularization_toolkit
name: Regularization Toolkit: Weight Decay, Dropout, Augmentation
description: The three families of regularization, what each constrains, and how to combine them without strangling the model.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Regularization Toolkit: Weight Decay, Dropout, Augmentation

## Purpose

Organize regularization into three families - constrain the weights,
perturb the network, enrich the data - so you pick the right tool for
your overfitting instead of stacking all of them blindly.

## When to use

- Held-out gap is wide and you need a plan, not a guess.
- Tuning a small model that memorizes instantly.
- Reviewing why a recipe combines several regularizers.

## Core ideas

1. **Constrain weights:** weight decay (AdamW) penalizes large
   weights, pushing the model toward simpler functions. Cheap, always
   on, tune in 0.01-0.1 for transformers.
2. **Perturb the network:** dropout randomly zeroes activations during
   training, forcing redundant representations - the model cannot rely
   on any single neuron. Rate 0.1 is the classic transformer default;
   at large scale dropout is often *removed* (data scale regularizes).
3. **Enrich the data:** augmentation and more data attack the root
   cause - the model memorizes because it can. Nothing regularizes
   like data the model hasn't seen.

Combine thoughtfully: weight decay + mild dropout is standard for
small transformers. Adding heavy augmentation on top of both can
underfit - regularization sums, and the bill comes due in train loss.

## Gotchas

- Dropout must be OFF at eval - a model that drops 10% of neurons at
  inference is just broken. (Frameworks handle this via train/eval
  mode; custom loops forget it.)
- Regularizing an underfitting model is the classic error: if train
  loss is high, you need capacity, not constraints.
- Label smoothing is regularization too (softens targets) - it stacks
  with the above.

## Quick reference

- Weights: AdamW decay. Network: dropout 0.1 (off at eval). Data:
  more/augment. Sum them carefully; diagnose underfit first.
