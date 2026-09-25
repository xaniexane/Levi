---
skill_id: ml_subword_tokenizers_compared
name: Subword Tokenizers Compared: BPE, WordPiece, Unigram
description: The three classic subword schemes, how their training objectives differ, and when each is used.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Subword Tokenizers Compared: BPE, WordPiece, Unigram

## Purpose

Compare the three dominant subword tokenization families - what each
optimizes during vocabulary learning, how encoding differs, and which
one you are actually using when you load a given model.

## When to use

- Choosing a tokenizer for a new model.
- Explaining why two models split the same word differently.
- Reading tokenizer configs and knowing what the fields mean.

## Core ideas

- **BPE:** merge the most frequent adjacent pair, repeat. Encoding
  applies merges greedily in learned order. Used by GPT-2/3/4-era
  models, RoBERTa, and LEVI's brain tokenizers.
- **WordPiece:** start from characters, repeatedly merge the pair that
  most increases *likelihood* of the training data under a unigram
  language model (not raw frequency). Encoding picks the longest-
  matching subword greedily left to right, with ## marking
  continuations. BERT's tokenizer.
- **Unigram (SentencePiece):** start from a large candidate set, prune
  down to target vocab by removing tokens whose removal hurts data
  likelihood least. Encoding uses Viterbi search for the globally best
  segmentation - probabilistic, can even sample segmentations.

All three share the goal: frequent strings become single tokens, rare
strings decompose, nothing is unrepresentable (byte fallback or
character coverage).

## Gotchas

- Tokenizer and model are a matched pair: swapping tokenizers on a
  trained model silently breaks everything (ids map to different
  strings).
- Fertility differences change effective context length: the same text
  can be 1.3x longer in tokens under a worse tokenizer.
- Pre-tokenization (splitting on spaces/punctuation before BPE) is part
  of the behavior - two "BPE" tokenizers with different pre-splitting
  disagree.

## Quick reference

- BPE: frequency merges. WordPiece: likelihood merges + longest match.
  Unigram: prune by likelihood + Viterbi segmentation.
