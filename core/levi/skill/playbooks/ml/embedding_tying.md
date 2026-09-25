---
skill_id: ml_embedding_tying
name: Tied Input/Output Embeddings
description: Sharing one matrix between the token embedding table and the output projection, and when it helps.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Tied Input/Output Embeddings

## Purpose

Explain weight tying: using the same matrix for the input token
embedding lookup and the final logits projection - why it is nearly
free performance, and when to untie.

## When to use

- Cutting parameters in a small model (embeddings are huge at large
  vocab).
- Understanding model_v2-style configs with tied embeddings.
- Debugging a shape mismatch between embedding and lm_head.

## Core ideas

The input embedding maps token id -> vector (vocab x d). The output
head maps vector -> logits over vocab (d x vocab). Tying sets
W_output = W_embed^T. Rationale: the representation that *recognizes*
a token coming in should resemble the representation that *predicts*
it going out - the same distributional knowledge serves both ends.

Savings are real: at vocab 8192 and d=384 (LEVI tiny-gpt-v2 scale)
the embedding table is ~3.1M parameters; tying avoids a second copy.
At vocab 128k and d=4096 it is over a billion parameters saved. Small
but consistent quality gains are usually observed too.

## Gotchas

- Tied weights get gradient contributions from both ends - usually
  fine, occasionally a source of instability with aggressive output-
  layer learning rates.
- Untying helps when input and output distributions genuinely differ
  (e.g. encoder-decoder with different vocabs per side).
- With tying, the lm_head has no separate bias unless you add one.

## Quick reference

- logits = h @ E^T where E is the embedding table. Saves vocab*d
  params; standard for decoder LMs.
