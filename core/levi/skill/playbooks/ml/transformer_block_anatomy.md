---
skill_id: ml_transformer_block_anatomy
name: Anatomy of a Transformer Block
description: The residual-plus-norm sandwich around attention and the feedforward network, and pre-norm vs post-norm.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Anatomy of a Transformer Block

## Purpose

Describe the repeating unit of a transformer: attention sublayer,
feedforward sublayer, residual connections, and normalization - and the
pre-norm vs post-norm ordering decision that changes training dynamics.

## When to use

- Implementing a transformer from scratch.
- Debugging unstable deep stacks.
- Reading model code and wondering where the norms go.

## Core ideas

One block transforms x into:

    x = x + Attention(Norm(x))        # sublayer 1
    x = x + FFN(Norm(x))              # sublayer 2

This is the **pre-norm** layout (norm inside the residual branch),
used by virtually all modern models including LEVI's tiny-gpt-v2. The
older **post-norm** layout (norm after the addition) trains fine at
small depth but becomes unstable as layers grow, because gradients must
pass through the norm at every layer boundary.

Residual connections are the load-bearing idea: each sublayer only has
to learn a *delta* on the representation, and gradients have a clean
highway through the additions. A 96-layer model is trainable because
each layer is a small perturbation, not a full rewrite.

## Gotchas

- Pre-norm models tend to have growing activation magnitudes with
  depth; final-layer norms and careful init matter.
- Dropping a residual (easy typo) turns the block into a pure function
  stack and kills gradient flow past a few layers.
- Norm placement must match between training and inference code - a
  mismatch silently degrades a loaded checkpoint.

## Quick reference

- Modern block: x + Sublayer(Norm(x)), twice (attention, then FFN).
- Pre-norm: stable at depth. Post-norm: original paper layout, fragile
  when deep.
