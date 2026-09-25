---
skill_id: ml_multi_head_attention
name: Multi-Head Attention
description: Why transformers run attention several times in parallel with smaller subspaces, and how heads specialize.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Multi-Head Attention

## Purpose

Explain why one attention mechanism is rarely enough: multi-head
attention splits the embedding into several smaller subspaces, runs
independent attention in each, and concatenates the results - letting
different heads track different relationships (syntax, coreference,
position) simultaneously.

## When to use

- Choosing n_head for a new model config.
- Interpreting what a trained model attends to.
- Understanding why head dimension matters for RoPE and kernels.

## Core ideas

Split d_model into h heads, each of dimension d_k = d_model / h. Each
head gets its own Q/K/V projections, so each learns a different
similarity metric. One head might learn "attend to the previous word",
another "attend to the subject of this verb". The outputs concatenate
and pass through a final linear projection W_o that mixes the heads
back together.

Head dimension is a real constraint: rotary embeddings need an even
head dimension, and fused kernels are happiest with powers of two
(64, 128). LEVI's tiny-gpt-v2 uses 6 heads over 384 dims, so head_dim =
64 - even, and friendly.

```python
def multi_head(X, heads):
    outs = [self_attention(X, h.Wq, h.Wk, h.Wv) for h in heads]
    return concat(outs, axis=-1) @ W_o
```

## Gotchas

- More heads is not automatically better; with a fixed d_model, more
  heads means thinner heads, each seeing less.
- Not every head is useful. Pruning studies routinely find dead or
  redundant heads - capacity is not the same as utilization.
- Attention maps are not explanations by themselves. A high weight
  means information flowed there, not that the model "decided" anything.

## Quick reference

- d_k = d_model / h; keep d_model divisible by h.
- Cost is roughly the same as single-head attention at the same width:
  splitting does not multiply FLOPs, it reorganizes them.
