---
skill_id: ml_vocab_size_tradeoffs
name: Vocabulary Size Tradeoffs
description: How vocab size trades embedding parameters against sequence length, and how to pick it for your model scale.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Vocabulary Size Tradeoffs

## Purpose

Explain the real tradeoff behind vocab size: bigger vocab means fewer
tokens per text (shorter sequences, cheaper attention) but a bigger
embedding table (more parameters, more memory) - and how to size it
for your model.

## When to use

- Picking vocab_size for a new tokenizer/model.
- Understanding why small models use small vocabs.
- Reading scaling discussions (vocab is often under-scaled).

## Core ideas

Parameters in the embedding table: vocab_size x d_model (doubled if
untied). At d=384, vocab 8192 -> ~3.1M params; vocab 128k -> ~49M -
larger than many small models' entire transformer stack. Meanwhile a
bigger vocab compresses text better: common phrases become single
tokens, so a fixed context window holds more text and attention (which
is quadratic in sequence length) does less work.

Rule of thumb: scale vocab with model size. Tiny models (10M params)
want 4k-16k; 7B-class models settled around 32k (LLaMA) while newer
ones push 128k+ for multilingual coverage, accepting the embedding
cost. LEVI's v2: 8192 vocab at 13.8M params - embedding table ~23% of
params when tied, a sane ratio.

## Gotchas

- Oversized vocab on a small model: most token embeddings barely train
  (rare tokens, few updates) - dead capacity.
- Undersized vocab: fertility explodes, context fills with fragments,
  effective intelligence per window drops.
- Changing vocab size after training is a full retrain, not a tweak.

## Quick reference

- Params: V*d (x2 untied). Bigger V: shorter sequences, bigger table.
  Size V with the model, not with ambition.
