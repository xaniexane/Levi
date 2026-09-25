---
skill_id: ml_cross_attention
name: Cross-Attention
description: How decoders attend into encoder states or other conditioning sequences, and where it shows up.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Cross-Attention

## Purpose

Explain cross-attention: queries come from one sequence (the decoder),
keys and values from another (the encoder output, an image embedding,
retrieved documents). This is how conditioning enters a transformer.

## When to use

- Building encoder-decoder models.
- Conditioning generation on retrieved text (RAG-style).
- Fusing modalities (text queries attending to image patches).

## Core ideas

Same formula as self-attention, different sources:

    Q = decoder_states @ Wq     # what the generator wants
    K = encoder_states @ Wk     # what the source offers
    V = encoder_states @ Wv

No causal mask over the encoder side - the whole source is visible.
The decoder still masks its own self-attention causally; the cross
attention lets each generated token pull from anywhere in the source.
In retrieval-augmented setups, the "encoder states" are simply the
encoded retrieved passages.

## Gotchas

- Cross-attention doubles the attention bookkeeping: two K/V sources
  to cache at inference.
- If the conditioning is weak (bad retrieval, uninformative encoder),
  the model learns to ignore it - cross-attention weights going
  uniform/diffuse is a symptom, not a bug in the mechanism.
- Length mismatch: encoder and decoder sequences differ in length, so
  the score matrix is rectangular (n_dec x n_enc), not square.

## Quick reference

- Cross-attention: Q from target, K/V from source. No future to mask
  on the source side.
