---
skill_id: ml_embedding_tables_and_lookup
name: Embedding Tables: Lookup, Memory, and Tying
description: The humble embedding layer as a giant lookup table: memory cost, gradient sparsity, and practical notes.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, embeddings]
version: 1.0.0
---
# Embedding Tables: Lookup, Memory, and Tying

## Purpose

Treat the embedding layer as what it is - a matrix you index into -
and cover the practical consequences: memory footprint, sparse
gradients, padding indices, and the tying decision.

## When to use

- Sizing model memory (embeddings are often the biggest single
  tensor).
- Debugging slow embedding updates or weird PAD behavior.
- Deciding tied vs untied output projections.

## Core ideas

`Embedding(vocab, d)` is a (vocab x d) matrix; forward pass is row
lookup by token id - O(1) per token, no matmul. Consequences:

- **Memory:** vocab*d floats. 128k x 4096 in fp32 = 2GB for one
  table. This is why vocab size is a memory decision first.
- **Sparse gradients:** each step only updates rows for tokens in the
  batch. Rare tokens train slowly - a real effect at large vocabs.
- **padding_idx:** the PAD row can be frozen at zero so padding never
  accumulates gradient noise.
- **Tying:** reuse the table transposed as the output projection
  (see the tying playbook) - halves the biggest tensor and usually
  helps slightly.

Initialization is usually small normal (std ~0.02); the table learns
purely from downstream error signal, so early in training it is noise
and everything downstream must cope with that.

## Gotchas

- Optimizer state (Adam m/v) doubles or triples the table's memory -
  count it when sizing.
- Row 0 is often PAD or UNK by convention; verify before assuming.
- With tying, the same rows serve both lookup and projection - a bug
  in one path corrupts both.

## Quick reference

- Cost is memory (V*d), updates are sparse per batch, freeze PAD,
  tie the output head unless you have a reason not to.
