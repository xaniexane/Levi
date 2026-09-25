---
skill_id: ml_rms_normalization
name: RMS Normalization
description: The simplified norm (no mean-centering) used by modern LLMs, and why dropping the mean is fine.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# RMS Normalization

## Purpose

Explain RMSNorm: LayerNorm without mean subtraction, just scaling by
the root-mean-square - cheaper, equally effective in practice, and the
default in most modern LLMs including LEVI's tiny-gpt-v2.

## When to use

- Reading modern model code (LLaMA-family, LEVI v2 brain).
- Squeezing out norm overhead in a tight training loop.
- Deciding between LayerNorm and RMSNorm for a new model.

## Core ideas

    rms = sqrt(sum(x^2)/d + eps)
    y = gain * x / rms

No mean computation, no bias term (in the usual formulation) - just
rescale to unit RMS and apply a learned gain. Empirically it matches
LayerNorm on language modeling while doing less work per token.
The intuition for why dropping the mean is harmless: the following
linear layer has its own bias and can reintroduce any shift the
network needs; what training actually needs is controlled *scale*,
which RMS provides.

LEVI's tiny-gpt-v2 uses RMSNorm in its pre-norm blocks paired with
RoPE and SwiGLU - the standard modern trio.

## Gotchas

- "Equally effective" is empirical, not proven; on some non-language
  tasks LayerNorm's centering still helps. Test, don't assume.
- Gain initialization to 1 matters; zero-initialized gain kills the
  signal at step 0.
- Same fp16 upcasting caveat as LayerNorm for the sum-of-squares.

## Quick reference

- y = g * x / sqrt(mean(x^2) + eps). Scale control without centering.
