---
skill_id: ml_self_attention_mechanism
name: Self-Attention: Queries, Keys, and Values
description: How self-attention lets every token weigh every other token, and what Q, K, V actually do.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Self-Attention: Queries, Keys, and Values

## Purpose

Explain the self-attention mechanism at the heart of every transformer:
how each position in a sequence builds a new representation by taking a
weighted mix of all positions, where the weights come from the data
itself rather than from a fixed pattern.

## When to use

- Reading or implementing transformer code and the Q/K/V projections
  feel like magic.
- Debugging attention-heavy behavior (repetition, ignoring context).
- Deciding what attention variant to use in a small model.

## Core ideas

Self-attention answers one question per position: "which other positions
should I listen to right now?" It does this with three linear
projections of the input, each with a distinct job:

- **Query (Q):** what this position is looking for. A question.
- **Key (K):** what each position offers. An index entry.
- **Value (V):** the actual content each position contributes once
  selected. The payload.

Score every query against every key with a dot product, scale, softmax
into weights, then mix the values by those weights. The output at
position i is a convex combination of all values, biased toward the
keys that matched its query.

```python
import math
def self_attention(X, Wq, Wk, Wv):
    Q, K, V = X @ Wq, X @ Wk, X @ Wv
    scores = (Q @ K.T) / math.sqrt(K.shape[1])
    weights = softmax(scores, axis=-1)      # rows sum to 1
    return weights @ V
```

## Gotchas

- Attention is permutation-invariant without position information; the
  mechanism itself has no notion of order. Positional encodings fix this.
- Dot products grow with dimension, so the sqrt(d_k) scaling is load
  bearing, not decoration. Without it the softmax saturates and
  gradients die.
- The softmax weights always sum to 1, so attention can never output
  "nothing" - even irrelevant context gets some weight. Masking exists
  to remove positions entirely.

## Quick reference

- scores[i,j] = dot(q_i, k_j) / sqrt(d_k)
- weights = softmax(scores); out_i = sum_j weights[i,j] * v_j
- Complexity: O(n^2 * d) time, O(n^2) memory for the score matrix.
