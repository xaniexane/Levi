---
skill_id: ml_special_tokens
name: Special Tokens: BOS, EOS, PAD, UNK, and Friends
description: What the control tokens mean, where each is required, and how misuse corrupts training.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Special Tokens: BOS, EOS, PAD, UNK, and Friends

## Purpose

Define the control tokens every tokenizer carries, state exactly where
each one belongs in the data pipeline, and flag the classic misuses
(training on PAD, forgetting EOS).

## When to use

- Preparing training batches.
- Debugging generation that never stops or stops immediately.
- Setting up a new tokenizer's special-token map.

## Core ideas

- **BOS (beginning of sequence):** marks sequence start. Optional for
  plain LM training (position 0 is start enough), required by some
  architectures.
- **EOS (end of sequence):** marks sequence end. The model learns to
  emit it to stop. Training data must include it, or the model never
  learns when to finish.
- **PAD:** fills batches to uniform length. Must be *masked out of the
  loss* - training the model to predict padding teaches it to emit
  padding.
- **UNK:** unknown token. With byte-fallback BPE it should almost
  never fire; if it does, something is off in preprocessing.
- **SEP/CLS/MASK:** encoder-era controls (BERT): separate segments,
  classify, mark masked positions.

Ids for specials are conventionally reserved at the top or bottom of
the vocab and added *after* BPE training so merges never produce them.

## Gotchas

- The #1 silent bug: loss computed over PAD positions. Always mask.
- Forgetting EOS in training targets -> rambling generations that only
  stop at max length.
- Two tokenizers' "<eos>" may be different ids - never assume, always
  read the tokenizer config.

## Quick reference

- EOS in targets (learn to stop). PAD masked from loss (never learn
  padding). UNK firing = preprocessing bug.
