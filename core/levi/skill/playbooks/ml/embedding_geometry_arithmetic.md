---
skill_id: ml_embedding_geometry_arithmetic
name: Embedding Geometry: Analogies and Vector Arithmetic
description: What king - man + woman + ... actually demonstrates, what it does not prove, and the limits of the party trick.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, embeddings]
version: 1.0.0
---
# Embedding Geometry: Analogies and Vector Arithmetic

## Purpose

Explain the famous vector-analogy phenomenon honestly: why
king - man + woman lands near queen in good embeddings, what
structural fact it reveals, and why it is a parlor trick rather than
proof of understanding.

## When to use

- Interpreting embedding spaces.
- Teaching what embeddings capture (relations, not definitions).
- Avoiding over-claims about "the model understands gender".

## Core ideas

If the training corpus consistently places "king" and "queen" in
parallel contexts differing along a "royalty + gender" axis, the
geometry can linearize that relation: the offset (queen - king) points
roughly the same way as (woman - man). Vector arithmetic then
"solves" analogies by parallelogram completion.

What it reveals: the embedding space has *linearly accessible*
relational structure - genuinely useful for retrieval and transfer.
What it does not reveal: understanding. The relation is a statistical
residue of how people write, complete with corpus biases (the classic
examples also encode stereotypes - geometry has no values, only
frequencies).

Modern contextual embeddings make the trick murkier - there is no
single vector per word anymore - but the underlying lesson stands:
linear structure in representation space is where simple downstream
models (probes, classifiers) do their work.

## Gotchas

- Analogy accuracy is a benchmark of the *corpus*, as much as the
  model. Biased text in, biased geometry out.
- Nearest-neighbor by cosine is not transitive and not calibrated -
  "close" means related, not equivalent.
- Do not read cognitive claims off vector arithmetic; read
  distributional ones.

## Quick reference

- Analogies work when relations are linear in embedding space - a
  property of the training distribution, not of comprehension.
