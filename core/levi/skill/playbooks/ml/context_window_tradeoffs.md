---
skill_id: ml_context_window_tradeoffs
name: Context Window Tradeoffs
description: What longer context costs (quadratic attention, KV-cache memory) and how to decide how much you need.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers, inference]
version: 1.0.0
---
# Context Window Tradeoffs

## Purpose

Explain the real costs of context length - quadratic attention
compute, linear-but-large KV cache - and how to pick a window size
for training vs serving.

## When to use

- Setting block_size / max_seq_len in a model config.
- Sizing serving memory for long-context use.
- Understanding context-extension work (RoPE scaling).

## Core ideas

Costs of sequence length n:

- **Attention compute:** O(n^2 * d) per layer. Doubling context
  quadruples attention FLOPs. (FlashAttention doesn't change the
  FLOPs, only the memory traffic.)
- **KV cache:** 2 * layers * heads * head_dim * n * bytes - linear in
  n, but the constant is brutal: tens of GB at 32k+ for 7B-class
  models in fp16.
- **Positional encoding:** RoPE angles / learned tables must cover n;
  extrapolating past trained length degrades without scaling tricks.

Longer context is genuinely useful (whole-codebase reasoning,
long-document QA), but most tokens in most tasks don't need it -
retrieval + short context often beats raw long context on
cost-adjusted quality. Train at the length your data supports
(LEVI's v2: block 512, train seq 128 - short because the corpus and
compute budget are small), extend deliberately later.

## Gotchas

- "Supports 128k" on a model trained at 4k means RoPE extrapolation
  - quality in the far tail is worse than the headline suggests.
  Check needle-in-haystack evals, not just the config.
- KV cache dominates serving cost long before attention FLOPs do.
- Training on short sequences then inferring long is the worst combo:
  positions never seen, cache never sized for.

## Quick reference

- Attention O(n^2), cache O(n) with a huge constant. Match trained
  length to data; extend with RoPE scaling + verification, not hope.
