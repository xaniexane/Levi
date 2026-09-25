---
skill_id: ml_batching_and_padding
name: Batching and Dynamic Padding
description: How variable-length sequences become rectangular batches, and minimizing the padding tax.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# Batching and Dynamic Padding

## Purpose

Explain the mechanics of batching variable-length sequences -
padding, attention masks, loss masks - and the standard tricks that
shrink padding waste.

## When to use

- Implementing a collate function.
- Debugging loss or attention bugs tied to PAD.
- Cutting the padding overhead in training or eval.

## Core ideas

Batches are rectangular: pad every sequence to the batch's max length
with PAD ids, and carry two masks:

- **Attention mask:** 0 on PAD so no token attends to padding (and
  padding positions' outputs are ignored).
- **Loss mask:** 0 on PAD (and on prompt tokens, for instruction
  tuning) so the model never trains to emit padding.

**Dynamic padding** pads to the longest *in the batch*, not a global
max - with shuffled data this alone cuts waste hugely. **Bucketing**
(groups of similar length batched together) cuts it further; packing
(see packing playbook) eliminates it.

Pad on the right for training (causal models); pad on the left for
batched *generation* (so the last real token aligns across the batch).

## Gotchas

- The loss mask and attention mask are different tensors with
  different jobs - conflating them is a classic bug source.
- Left vs right padding must match the use: wrong side in generation
  shifts every position id.
- Some tokenizers lack a PAD id - set one (often EOS) explicitly and
  mask it everywhere.

## Quick reference

- Pad to batch max (dynamic), mask PAD in attention and loss, pad
  right for train / left for generation batches.
