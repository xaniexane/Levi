---
skill_id: ml_sequence_packing
name: Sequence Packing
description: Filling every training sequence to the brim with multiple documents: throughput win, masking discipline.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# Sequence Packing

## Purpose

Explain sequence packing: concatenate short documents with separators
until each training row is full - eliminating padding waste at the
cost of cross-document attention you must handle.

## When to use

- Training on documents much shorter than the context window.
- Padding waste above ~20% of tokens.
- Understanding "packed" vs "padded" in training configs.

## Core ideas

Without packing, a batch of 200-token documents in a 2048 window
wastes 90% of compute on PAD. Packing concatenates documents
(doc1 + EOS + doc2 + EOS + ...) to fill the window - near-100%
token utilization, ~2-5x throughput on short-doc corpora.

The catch: causal attention now lets doc2 attend to doc1. Fixes:

- **Block-diagonal masking:** attention mask restricts each token to
  its own document. Exact, some kernel support needed.
- **Accept it:** many pipelines skip the mask; the model learns the
  EOS boundary means "new document". Slightly noisy, widely used,
  mostly harmless at scale.

Position ids restart per document in careful implementations
(else doc2's positions continue from doc1's - usually harmless with
RoPE, but restart is cleaner).

## Gotchas

- Eval on packed data needs the same masking decision, or numbers
  aren't comparable.
- Document order within a pack is a (weak) signal - shuffle documents
  before packing.
- Packing + gradient accumulation composes fine; packing + naive
  per-document loss weighting needs care.

## Quick reference

- Pack: concat docs with separators to fill the window. Mask
  cross-doc attention (or accept EOS-boundary learning). Utilization
  -> ~100%.
