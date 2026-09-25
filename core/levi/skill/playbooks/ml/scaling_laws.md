---
skill_id: ml_scaling_laws
name: Neural Scaling Laws
description: How loss scales with parameters, data, and compute - and the Chinchilla lesson about balanced scaling.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Neural Scaling Laws

## Purpose

Explain scaling laws: the empirical power-law relationships between
compute/parameters/data and loss, and the practical rule they imply -
scale all three together, not just the model.

## When to use

- Planning training compute budgets.
- Deciding model size vs training tokens.
- Understanding why "just make it bigger" stopped working alone.

## Core ideas

Across orders of magnitude, test loss falls as a power law in each of
parameters (N), data (D), and compute (C) - when the other two aren't
bottlenecking. The landmark correction was **Chinchilla**: earlier
recipes undertrained big models (too few tokens per parameter). The
compute-optimal balance is roughly **20 tokens per parameter** -
a 70B model wants ~1.4T tokens, not 300B.

Implications for small builders: a 13.8M-param model (LEVI v2 scale)
is compute-optimal near ~276M tokens - far more than a hobby corpus.
Small models are therefore *always* data-starved relative to the
optimum; the honest goal shifts from "optimal" to "proof of learning"
(loss falls, held-out tracks, pipeline works).

Scaling laws also have floors: irreducible entropy of the data
(Bayesian limit) - loss asymptotes, it never hits zero.

## Gotchas

- Power laws describe the *frontier*; a bad implementation sits above
  it at every scale. Laws don't excuse sloppy training.
- The 20:1 ratio assumes single-epoch training on fresh data;
  repeating data (multi-epoch small corpora) has diminishing returns
  past ~4 epochs.
- Inference cost scales with N but not D - a smaller model trained
  longer (overtrained per Chinchilla) can be the right product call.

## Quick reference

- Loss ~ power law in N, D, C. Compute-optimal ~= 20 tokens/param.
  Small models: aim for proof-of-learning, not the frontier.
