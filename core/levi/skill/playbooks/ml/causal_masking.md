---
skill_id: ml_causal_masking
name: Causal Masking for Autoregressive Models
description: How the triangular mask enforces left-to-right generation, and why training can still be parallel.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Causal Masking for Autoregressive Models

## Purpose

Explain the causal (look-ahead) mask: the simple triangular trick that
lets a decoder train on all positions in parallel while still only
ever seeing the past - which is what makes autoregressive generation
valid.

## When to use

- Training any left-to-right language model.
- Debugging a model that seems to "cheat" (suspiciously low loss).
- Understanding why generation is sequential but training is parallel.

## Core ideas

During training, the whole target sequence is fed in at once, shifted
by one position: the model predicts token t+1 from tokens 1..t. To
prevent position t from peeking at positions t+1 and beyond, add
negative infinity to the upper triangle of the score matrix before the
softmax. Softmax of -inf is 0, so future positions get exactly zero
weight.

```python
import numpy as np
def causal_mask(n):
    m = np.zeros((n, n))
    m[np.triu_indices(n, k=1)] = -1e9   # future -> -inf-ish
    return m
scores = Q @ K.T / math.sqrt(d_k) + causal_mask(n)
```

At inference there is no future yet, so generation proceeds one token
at a time, appending each new token to the context.

## Gotchas

- Forgetting the mask (or applying it on the wrong triangle) gives a
  model that memorizes the future: train loss looks amazing, generated
  text is garbage. Classic silent bug.
- -inf in float16 can overflow to NaN in some softmax implementations;
  large negative constants like -1e4 are safer in low precision.
- Prefix-LM / bidirectional-prefix variants mask differently: the
  prompt region is fully visible, only the generated tail is causal.

## Quick reference

- Mask: scores[i, j] = -inf for j > i; softmax kills future weights.
- Training: parallel over positions. Inference: sequential, one step
  per token.
