---
skill_id: ml_rotary_positional_embeddings
name: Rotary Positional Embeddings (RoPE)
description: How rotating query/key vectors by position-dependent angles bakes relative position into attention scores.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Rotary Positional Embeddings (RoPE)

## Purpose

Explain RoPE: instead of adding position vectors, rotate each
query/key 2D chunk by an angle proportional to its position. Attention
scores then depend on *relative* distance automatically - the current
standard for long-context models, and what LEVI's tiny-gpt-v2 uses.

## When to use

- Configuring position handling in any modern decoder.
- Extending context length (RoPE scaling: NTK, YaRN, linear).
- Debugging why head_dim must be even.

## Core ideas

Split each q/k vector into pairs. For pair i at position m, rotate by
angle m * theta_i, where theta_i = base^(-2i/d) (same geometric
spacing as sinusoids). The dot product of rotated q_m and k_n depends
only on (m - n): absolute positions cancel, relative distance remains.
No position vectors are added to the embeddings at all - position
lives in the rotation.

```python
# sketch: rotate each consecutive pair (x0, x1) by angle a
def rope_pair(x0, x1, a):
    return x0*cos(a) - x1*sin(a), x0*sin(a) + x1*cos(a)
```

Head dimension must be even (pairs), which is why configs like 64 or
128 per head are standard. The `base` (often 10000, larger for long
context) controls how fast angles grow with distance.

## Gotchas

- RoPE is applied to Q and K only, never to V - values carry content,
  not position.
- Naive extrapolation past the trained length degrades: angles wrap
  into regimes never seen. Scaling methods adjust the base or the
  angles to compensate.
- KV-cache + RoPE: cache the *unrotated* K and rotate at query time, or
  the cached angles go stale as positions shift. Most implementations
  rotate before caching with absolute positions - get this wrong and
  long generations drift.

## Quick reference

- angle(m, i) = m * base^(-2i/d); rotate q/k pairs; score depends on
  m - n only.
