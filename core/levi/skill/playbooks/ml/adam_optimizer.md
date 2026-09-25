---
skill_id: ml_adam_optimizer
name: Adam Optimizer
description: Per-parameter adaptive learning rates from gradient moments, bias correction, and why Adam trains transformers.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Adam Optimizer

## Purpose

Explain Adam - the default optimizer for transformer training - as
momentum plus per-parameter scaling: each parameter gets its own
effective learning rate from its gradient history.

## When to use

- Training any transformer (Adam/AdamW is the default for a reason).
- Debugging Adam-specific pathologies (non-convergence, late spikes).
- Setting betas and epsilon sensibly.

## Core ideas

Track two moving averages per parameter:

    m = b1*m + (1-b1)*g        # first moment: momentum
    v = b2*v + (1-b2)*g^2      # second moment: scale estimate
    m_hat = m/(1-b1^t); v_hat = v/(1-b2^t)   # bias correction
    theta = theta - lr * m_hat/(sqrt(v_hat) + eps)

Each parameter steps ~lr in size, divided by its typical gradient
magnitude: frequently-updated parameters (embeddings of common tokens)
get damped, rarely-updated ones get boosted. This adaptivity is why
Adam trains transformers where SGD struggles - attention and
embedding gradients span orders of magnitude.

Bias correction matters early: m and v start at 0, so without the
/(1-b^t) terms the first steps would be tiny. Defaults b1=0.9,
b2=0.999, eps=1e-8 are battle-tested; eps sometimes raised to 1e-6 in
fp16 for stability.

## Gotchas

- Adam can converge to sharp minima that generalize worse than SGD's
  - the "Adam generalization gap". AdamW + proper decay mostly closes
  it.
- v's long memory (b2=0.999) means stale curvature estimates after
  distribution shifts; fine-tuning sometimes wants lower b2.
- eps is not innocent: with tiny gradients, eps dominates the
  denominator and acts as a hidden learning-rate cap.

## Quick reference

- m: direction memory. v: per-param scale memory. Step ~ lr *
  m_hat/(sqrt(v_hat)+eps). Defaults: b1 .9, b2 .999, eps 1e-8.
