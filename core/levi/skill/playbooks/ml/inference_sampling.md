---
skill_id: ml_inference_sampling
name: Sampling: Temperature, Top-k, Top-p
description: How next-token probabilities become text: greedy vs sampling, and what temperature/top-k/top-p actually control.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, inference]
version: 1.0.0
---
# Sampling: Temperature, Top-k, Top-p

## Purpose

Explain the decoding step that turns logits into tokens - greedy,
temperature sampling, top-k, top-p (nucleus) - and how to choose
settings for factual vs creative generation.

## When to use

- Configuring generation for a served model.
- Debugging repetitive or incoherent outputs.
- Understanding eval harness generation settings.

## Core ideas

Logits -> probabilities via softmax( logits / T ):

- **T -> 0 (greedy):** always the argmax. Deterministic,
  highest-probability text - often dull and prone to repetition
  loops.
- **T = 1:** sample the raw distribution. T > 1 flattens (more
  random), T < 1 sharpens (more conservative). 0.7 is the common
  "sensible but not robotic" setting.

Truncation methods cut the tail before sampling:

- **Top-k:** keep the k most likely tokens, renormalize. k=40-50
  classic.
- **Top-p (nucleus):** keep the smallest set whose cumulative
  probability >= p (p=0.9-0.95). Adapts: sharp distributions keep
  few tokens, flat ones keep many. Generally preferred over top-k.

Repetition penalties / frequency penalties separately discourage
re-emitting tokens - a patch for the greedy-loop pathology, not a
sampling method per se.

## Gotchas

- Sampling settings change benchmark scores: report them with any
  generation eval, or the number is meaningless.
- High temperature doesn't make a model "creative" - it makes it
  higher-entropy. Structure still comes from the model.
- For deterministic pipelines (evals, tests), use greedy or fixed
  seeds; sampled outputs are not reproducible otherwise.

## Quick reference

- T scales sharpness (0.7 sensible default). Top-p 0.9-0.95 adapts
  the candidate set. Greedy for determinism, sampling for variety.
  Always report settings with evals.
