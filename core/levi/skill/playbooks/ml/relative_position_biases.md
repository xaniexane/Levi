---
skill_id: ml_relative_position_biases
name: Relative Position Biases (T5-style and ALiBi)
description: Adding learned or fixed distance penalties directly to attention scores instead of rotating vectors.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Relative Position Biases (T5-style and ALiBi)

## Purpose

Cover the other family of position handling: add a bias term to each
attention score based on the distance between query and key positions -
learned buckets (T5) or a fixed linear penalty (ALiBi).

## When to use

- Understanding T5/older long-context literature.
- Needing extrapolation-friendly position handling without RoPE.
- Comparing position schemes for a new architecture.

## Core ideas

Score becomes:

    score[i,j] = dot(q_i, k_j)/sqrt(d) + bias(i - j)

T5 learns the bias per distance bucket (log-spaced buckets, so far
distances share coarse buckets) - flexible, parameterized. ALiBi uses
a fixed, non-learned penalty: each head subtracts m * (i - j) for keys
before the query, with a different slope m per head. Nearby tokens get
near-zero penalty, distant tokens get pushed down hard.

ALiBi's appeal is extrapolation: the penalty is a simple function of
distance, so positions far beyond training length still get *some*
sensible bias, where RoPE angles would be out of distribution.

## Gotchas

- ALiBi biases strongly toward recency; tasks needing uniform long-
  range attention can suffer.
- Learned T5 buckets add parameters per layer but are tiny compared to
  the rest of the model.
- Mixing schemes (RoPE + ALiBi) is occasionally tried but they encode
  overlapping information - usually redundant.

## Quick reference

- T5: bias = learned_embedding[bucket(i-j)].
- ALiBi: bias = -m_head * max(0, i - j), fixed slopes per head.
