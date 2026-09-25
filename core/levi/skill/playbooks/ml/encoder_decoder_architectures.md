---
skill_id: ml_encoder_decoder_architectures
name: Encoder, Decoder, and Encoder-Decoder Architectures
description: When to use bidirectional encoders, causal decoders, or the full seq2seq pair - and what each is for.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Encoder, Decoder, and Encoder-Decoder Architectures

## Purpose

Sort out the three transformer families: encoders (bidirectional,
representation-first), decoders (causal, generation-first), and
encoder-decoder pairs (seq2seq) - so you pick the right shape for the
job instead of defaulting to whatever is fashionable.

## When to use

- Choosing an architecture for classification, embedding, or generation.
- Understanding why BERT-style and GPT-style models train differently.
- Reading older seq2seq literature (translation, summarization).

## Core ideas

- **Encoder-only** (e.g. BERT family): no causal mask, every token sees
  every token. Trained with masked-language modeling. Best for
  understanding tasks: classification, retrieval embeddings, NER.
- **Decoder-only** (e.g. GPT family, LEVI's tiny-gpt-v2): causal mask,
  predicts next token. Best for generation and for the modern
  do-everything LLM.
- **Encoder-decoder** (e.g. T5 family): encoder reads the input
  bidirectionally, decoder generates with cross-attention into the
  encoder states. Natural fit for translation and conditional
  generation, at the cost of more machinery.

The field converged on decoder-only for general models because one
simple objective (next-token prediction) scales cleanly, not because
encoders are worse at understanding.

## Gotchas

- Decoder-only models can do classification too (prompt it, read the
  logits), but encoder embeddings are cheaper per query for retrieval.
- Encoder-decoder doubles several hyperparameters (two stacks, cross
  attention) - more knobs, more ways to misconfigure.
- "Bidirectional" at inference for decoders requires tricks (fill-in-
  the-middle training); it is not free.

## Quick reference

- Understand -> encoder. Generate -> decoder. Conditioned generation
  with clean separation -> encoder-decoder.
