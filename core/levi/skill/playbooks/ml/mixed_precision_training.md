---
skill_id: ml_mixed_precision_training
name: Mixed Precision Training
description: Training in fp16/bf16 with fp32 master weights: what halves, what stays full, and loss scaling.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Mixed Precision Training

## Purpose

Explain mixed precision: run the expensive matmuls in 16-bit,
keep master weights and sensitive ops in fp32 - ~2x faster, ~half the
memory, with numerics you have to respect.

## When to use

- Any GPU training (this is default-on in modern stacks).
- Debugging NaNs that appear only in fp16.
- Choosing fp16 vs bf16.

## Core ideas

Weights stored fp32 (master copy); each step casts to fp16/bf16 for
forward+backward, then the fp32 master is updated. fp16 halves memory
bandwidth and doubles tensor-core throughput. Two numerical hazards:

1. **Gradient underflow:** fp16's smallest normal is ~6e-5; small
   gradients flush to zero. Fix: **loss scaling** - multiply loss by S
   (e.g. 2^16) before backward, unscale gradients before the update.
   Dynamic scaling adjusts S automatically.
2. **Overflow:** fp16 max is 65504; large activations (logits sums,
   LayerNorm variance) overflow. Fix: keep norms/softmax in fp32, or
   use **bf16** - same exponent range as fp32 (no overflow/underflow
   drama), less mantissa precision. bf16 is the safer default where
   hardware supports it.

## Gotchas

- Loss scaling + gradient clipping order: unscale, then clip, then
  step. Wrong order clips scaled gradients (nonsense threshold).
- Some ops (reductions, norms) must stay fp32 - autocast handles the
  standard list; custom kernels need manual care.
- NaN on step N in fp16 that vanishes in fp32: almost always overflow
  in a reduction - find it, upcast it.

## Quick reference

- fp32 master weights, fp16/bf16 compute. fp16 needs loss scaling;
  bf16 usually doesn't. Unscale -> clip -> step.
