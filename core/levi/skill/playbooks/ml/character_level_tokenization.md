---
skill_id: ml_character_level_tokenization
name: Character-Level Tokenization
description: Why tiny models like LEVI's first brain train on raw characters, and what character models gain and lose.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Character-Level Tokenization

## Purpose

Explain character-level modeling: vocab = the alphabet (plus a few
controls), sequences get long, but the model learns spelling,
morphology, and robustness from first principles - the approach behind
LEVI's original tiny char-level GPT.

## When to use

- Understanding LEVI's first brain (train.py: char-level GPT).
- Deciding tokenization for a tiny model or a noisy-text domain.
- Reasoning about robustness to typos and novel words.

## Core ideas

Vocabulary: ~100 symbols (letters, digits, punctuation, whitespace).
No tokenizer training, no OOV problem, no fertility surprises across
languages. The model must learn that "c"+"a"+"t" forms a unit - which
costs sequence length: a 512-token BPE context is ~2000 characters,
so char models need 4x the context for the same text, and attention
cost grows quadratically with that.

The payoff is robustness and honesty: typos are just character
sequences, novel words decompose naturally, and there is no hidden
tokenizer doing half the linguistic work. For a proof-of-learning
brain (LEVI's stage-1 goal: demonstrate the loop works), character
level is the right call - the corpus pipeline stays stdlib-simple and
the model genuinely learns spelling.

## Gotchas

- Long sequences make attention expensive; char models need shorter
  effective text per context window.
- Sample quality at small scale is worse than subword models -
  characters are a harder prediction problem per step.
- Byte-level (256 tokens) is the modern compromise: fixed small vocab
  like chars, but multibyte UTF-8 keeps sequences shorter for
  non-ASCII text.

## Quick reference

- Vocab ~100, no training, no OOV. Cost: ~4x sequence length vs BPE.
  Best for: tiny models, noisy text, proof-of-learning pipelines.
