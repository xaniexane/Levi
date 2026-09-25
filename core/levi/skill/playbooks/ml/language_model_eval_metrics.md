---
skill_id: ml_language_model_eval_metrics
name: Language Model Evaluation Beyond Perplexity
description: Accuracy, bits-per-byte, downstream benchmarks, and human eval: what PPL misses and how to cover it.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, evaluation]
version: 1.0.0
---
# Language Model Evaluation Beyond Perplexity

## Purpose

Cover the eval battery past perplexity: token accuracy, tokenizer-
agnostic bits-per-byte, task benchmarks, and why you need all of them
- PPL alone underdescribes a model.

## When to use

- Evaluating a trained checkpoint seriously.
- Writing an eval harness (cf. eval.py / eval_gate.py patterns).
- Deciding which checkpoint to keep.

## Core ideas

- **Token accuracy:** fraction of positions where argmax prediction
  equals the true token. Crude but interpretable; correlates with PPL
  but saturates differently.
- **Bits per byte (BPB):** total negative log-likelihood in bits
  divided by UTF-8 bytes of text. Tokenizer-agnostic - the honest way
  to compare models with different vocabs. Lower is better.
- **Downstream tasks:** classification/QA/generation benchmarks probe
  capabilities PPL can't see (reasoning, instruction following).
  A model can have decent PPL and zero task ability.
- **Generation samples:** fixed prompts, human-readable outputs.
  LEVI's eval writes samples.md for exactly this - numbers don't show
  degenerate repetition, samples do.
- **Eval gates:** hard thresholds (PPL below X, no NaN, samples sane)
  that a checkpoint must pass before promotion. Automate the bar.

## Gotchas

- Benchmark contamination (test text in training data) inflates
  downstream scores - dedup eval against train.
- Single-number evals get gamed; batteries resist it.
- Human eval is the gold standard for generation quality and the most
  expensive - use it last, on finalists.

## Quick reference

- PPL for training signal, BPB for cross-tokenizer comparison,
  benchmarks for capability, samples for sanity, gates for
  automation.
