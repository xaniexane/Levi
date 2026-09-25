---
skill_id: ml_flash_attention_concept
name: FlashAttention: the Concept
description: Why attention is memory-bound, not compute-bound, and how tiling plus online softmax fixes it.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# FlashAttention: the Concept

## Purpose

Explain the key insight of FlashAttention without kernel code: standard
attention materializes the full n x n score matrix in slow GPU memory,
and the win comes from never materializing it - tiling the computation
through fast on-chip SRAM with an online (streaming) softmax.

## When to use

- Understanding why long-context training became feasible.
- Deciding whether you need the fused kernel (you almost always do).
- Reasoning about memory vs compute bottlenecks in attention.

## Core ideas

Standard attention writes the n x n scores to HBM (GPU main memory),
reads them back for softmax, writes again, reads again for the V
multiply. HBM bandwidth, not FLOPs, is the bottleneck. FlashAttention
tiles Q, K, V into blocks that fit in SRAM, computes partial softmax
statistics per block, and rescales as it goes (online softmax keeps a
running max and normalizer). The full matrix is never stored; memory
drops from O(n^2) to O(n), and wall-clock speedups of 2-4x are typical
because SRAM is ~20x faster than HBM.

Exactness matters: unlike sparse/low-rank approximations, this is
*exact* attention - same math, different memory traffic. That is why it
was adopted universally instead of remaining a research curiosity.

## Gotchas

- It is an implementation technique, not a model change: checkpoints
  are interchangeable with naive attention.
- Causal masking and dropout need kernel support; check the variant.
- On CPU or tiny sequences the tiling overhead can make it slower -
  the win is for long sequences on accelerators.

## Quick reference

- Bottleneck: HBM reads/writes of the n x n matrix. Fix: tile in
  SRAM, online softmax, never materialize. Result: exact, O(n) memory.
