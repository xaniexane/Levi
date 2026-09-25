---
skill_id: ml_layer_normalization
name: Layer Normalization
description: What LayerNorm computes, why transformers depend on it, and the learnable gain and bias.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Layer Normalization

## Purpose

Define LayerNorm precisely - normalize across the feature dimension per
token - and explain why it stabilizes transformer training where batch
statistics cannot.

## When to use

- Implementing or debugging normalization in a transformer.
- Understanding pre-norm vs post-norm training stability.
- Choosing epsilon and initialization for norm layers.

## Core ideas

For a vector x of dimension d:

    mean = sum(x)/d ; var = sum((x-mean)^2)/d
    y = gain * (x - mean)/sqrt(var + eps) + bias

Unlike BatchNorm, statistics are computed per token, not per batch -
so it works with batch size 1, variable lengths, and autoregressive
decoding, all of which break batch statistics. The learnable gain
(initialized to 1) and bias (initialized to 0) let the network undo
the normalization if some layer wants raw magnitudes.

Placement (pre-norm: norm inside the residual branch) is what makes
deep stacks trainable: gradients flow through the residual additions
unimpeded, and each sublayer sees normalized inputs.

## Gotchas

- eps exists to avoid division by zero; too-large eps silently weakens
  normalization. 1e-5 is the common default.
- LayerNorm has no running statistics to track - simpler than
  BatchNorm, which is part of why transformers adopted it.
- In fp16, the variance computation can overflow; many implementations
  upcast to fp32 inside the norm.

## Quick reference

- Normalize over features per token: y = g*(x-mu)/sqrt(var+eps) + b.
- Per-token stats -> batch-size independent, autoregressive-safe.
