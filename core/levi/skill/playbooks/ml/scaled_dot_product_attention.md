---
skill_id: ml_scaled_dot_product_attention
name: Scaled Dot-Product Attention
description: The exact scoring formula behind attention, why the scaling factor exists, and when scores saturate.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Scaled Dot-Product Attention

## Purpose

Pin down the single formula that scores query/key pairs, explain why
dividing by sqrt(d_k) is necessary, and show the failure mode (softmax
saturation) it prevents.

## When to use

- Implementing attention from scratch.
- Debugging training that stalls with attention weights stuck near
  one-hot or near-uniform.
- Choosing between dot-product and additive attention variants.

## Core ideas

For queries Q and keys K of dimension d_k:

    Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V

The dot product of two random vectors of dimension d_k has variance
d_k, so unscaled scores grow like sqrt(d_k). Feed those into a softmax
and the largest score dominates completely: the softmax output goes
near one-hot, its gradients go near zero, and learning freezes. Dividing
by sqrt(d_k) normalizes the score variance back to ~1, keeping the
softmax in its responsive middle range.

## Gotchas

- Saturation is silent: loss may still creep down while attention
  gradients are effectively dead. If weights look one-hot from step
  one, check scaling before blaming data.
- Additive (Bahdanau-style) attention avoids the scaling issue with a
  small feedforward scorer, but costs more compute; dot-product won
  because it is fast and parallel.
- Temperature tricks (dividing by extra factors) change sharpness at
  inference; they are a different knob from the training-time scaling.

## Quick reference

- scores = Q K^T / sqrt(d_k); softmax over the key axis.
- Var(dot(q,k)) ~ d_k for unit-variance components -> scale by 1/sqrt(d_k).
