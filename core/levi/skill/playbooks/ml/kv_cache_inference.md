---
skill_id: ml_kv_cache_inference
name: KV Cache for Autoregressive Inference
description: How caching keys and values turns generation from quadratic to linear per token, and what it costs in memory.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# KV Cache for Autoregressive Inference

## Purpose

Explain the KV cache: during generation, keys and values for past
tokens never change, so recompute them once, cache them, and each new
token only computes its own q/k/v and attends over the cache.

## When to use

- Serving any autoregressive model (this is always on in practice).
- Sizing GPU memory for long-context serving.
- Debugging slow or memory-hungry generation.

## Core ideas

Without caching, generating token t recomputes attention over all t
tokens from scratch: total O(n^2) work for n tokens. With the cache,
step t computes one query and attends over t cached keys: O(t) per
step, O(n^2) total but with a tiny constant - and in practice the per-
step work is dominated by the model weights, not attention.

The price is memory: 2 (K and V) x layers x heads x head_dim x
sequence_length x bytes-per-element. For a 7B-class model at 32k
context in fp16 this is tens of GB - often larger than the weights.
This is why quantization of the KV cache, paged attention, and
eviction policies (keep recent + "attention sink" tokens) exist.

```python
# per step: only the new token is projected
q_new, k_new, v_new = project(x_new)
K_cache.append(k_new); V_cache.append(v_new)
out = softmax(q_new @ K_cache.T / sqrt(d)) @ V_cache
```

## Gotchas

- Batch serving with different sequence lengths fragments the cache;
  paged/blocked allocators (vLLM-style) fix the waste.
- Sampling parameters (temperature, top-p) do not touch the cache -
  but changing the prompt mid-generation invalidates it.
- RoPE interacts with caching: rotate with absolute positions before
  caching, or recompute consistently.

## Quick reference

- Cache K/V per layer per past token; per-step cost O(seq_len).
- Memory: 2 * n_layers * n_heads * head_dim * seq_len * bytes.
