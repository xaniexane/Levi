---
skill_id: ml_word_embeddings_distributional
name: Word Embeddings and the Distributional Hypothesis
description: Why words become vectors: meaning from co-occurrence, and what embedding tables actually store.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, embeddings]
version: 1.0.0
---
# Word Embeddings and the Distributional Hypothesis

## Purpose

Explain the foundational idea behind all embeddings - "a word is
characterized by the company it keeps" - and what a trained embedding
table represents geometrically.

## When to use

- First-principles understanding before transformers.
- Debugging why similar words cluster in embedding space.
- Explaining embeddings to someone new to ML.

## Core ideas

The distributional hypothesis: words appearing in similar contexts
have similar meanings. Train a model to predict a word from its
context (or vice versa), and the internal word vectors - the rows of
the embedding table - arrange themselves so that distributional
similarity becomes geometric closeness. "Cat" and "dog" end up nearby
not because anyone labeled them animals, but because both appear near
"pet", "vet", "fed".

In transformers this table is just the first layer: token id in,
vector out, then everything else operates on vectors. The table is
trained jointly with the whole model, so its geometry serves the
model's objective - next-token prediction - not any human notion of
meaning. Static embeddings (word2vec-era) froze one vector per word;
contextual embeddings (transformers) build the vector fresh per
occurrence, so "bank" differs by sentence.

## Gotchas

- Embedding similarity is distributional, not definitional: antonyms
  ("hot"/"cold") often sit close together - they share contexts.
- Rare words get poor embeddings: few updates, noisy position.
- The embedding table is a lookup, not a computation - its cost is
  memory, and its quality bounds everything downstream.

## Quick reference

- Meaning from co-occurrence; geometry encodes distributional
  similarity. Contextual > static: one vector per occurrence, not per
  word.
