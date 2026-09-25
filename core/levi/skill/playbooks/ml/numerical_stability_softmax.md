---
skill_id: ml_numerical_stability_softmax
name: Numerical Stability: the Log-Sum-Exp Trick
description: Why naive softmax overflows, how log-sum-exp fixes it, and where else the trick applies.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training, math]
version: 1.0.0
---
# Numerical Stability: the Log-Sum-Exp Trick

## Purpose

Explain the single most-used numerical trick in deep learning:
subtract the max before exponentiating - making softmax and
cross-entropy safe across precisions.

## When to use

- Implementing softmax, cross-entropy, or attention scores by hand.
- Debugging NaN/inf in fp16 training.
- Any log(sum(exp(...))) computation.

## Core ideas

Naive softmax: exp(x_i)/sum(exp(x_j)). If any x_i is large (say 100),
exp overflows to inf - even in fp32 past ~88. The fix:

    m = max(x)
    softmax(x)_i = exp(x_i - m) / sum_j exp(x_j - m)

Subtracting the max is mathematically exact (it factors out of
numerator and denominator) and bounds the largest exponent at
exp(0) = 1. For cross-entropy, fold it into log_softmax:

    L = -x_true + m + log(sum_j exp(x_j - m))

- one stable expression, no intermediate softmax needed. The same
pattern (subtract max, exponentiate, correct afterward) applies to
any log-sum-exp, including the online softmax inside FlashAttention.

## Gotchas

- In fp16, even the *shifted* exps can underflow for very negative
  values - usually harmless (they contribute ~0), but the max term
  itself must be representable.
- Libraries do this internally; you need it when writing custom
  kernels, losses, or numpy prototypes.
- log(sum(exp)) without the trick is the #1 source of "works in
  float64, NaNs in float16".

## Quick reference

- softmax: subtract max first. Cross-entropy: use log_softmax form.
  Applies to every log-sum-exp you'll ever write.
