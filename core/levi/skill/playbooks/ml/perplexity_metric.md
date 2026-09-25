---
skill_id: ml_perplexity_metric
name: Perplexity
description: The canonical language-model metric: exp of cross-entropy, what it means, and how to compare it honestly.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, evaluation]
version: 1.0.0
---
# Perplexity

## Purpose

Define perplexity rigorously - exponentiated average negative log-
likelihood - build intuition for its scale, and state the rules for
honest comparison.

## When to use

- Reporting or reading LM evaluation numbers.
- Sanity-checking a training run (PPL should fall smoothly).
- Comparing models or checkpoints.

## Core ideas

    PPL = exp( - (1/N) * sum_i log p(x_i | context) )

"Perplexity 125" means: the model is as surprised by this text, on
average, as if it were choosing uniformly among 125 options per
token. Lower is better; 1.0 is perfect prediction (unattainable on
real text). LEVI's tiny-gpt-v2 reported held-out PPL 125.01 at
completion - fluent-ish texture, far from sharp prediction, exactly
what a 13.8M-char/subword model on web text earns.

PPL decomposes: it is exp(cross-entropy loss). A loss drop of 0.1
multiplies PPL by e^-0.1 ~= 0.905 - ~10% less perplexed. Small loss
moves are bigger deals than they look.

## Gotchas

- PPL is tokenizer-relative: fewer tokens per text (bigger vocab)
  mechanically lowers per-token PPL. Never compare PPL across
  tokenizers.
- PPL averages over *all* tokens equally - predictable boilerplate
  dilutes the number. Sliced PPL (by token type) is more informative.
- Low PPL != good generation. It measures prediction, not usefulness;
  degenerate repetitive text can have great PPL.

## Quick reference

- PPL = e^(cross-entropy). Tokenizer-relative; compare only within
  one tokenizer. Falling PPL = learning; PPL 1 = impossible ideal.
