---
skill_id: ml_cross_entropy_loss
name: Cross-Entropy Loss for Language Modeling
description: The one loss that trains nearly every language model: what it measures and why it matches next-token prediction.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Cross-Entropy Loss for Language Modeling

## Purpose

Define cross-entropy loss precisely, show why it is the natural
objective for next-token prediction, and connect it to perplexity.

## When to use

- Implementing or debugging LM training.
- Understanding what "loss 3.6" actually means.
- Choosing between loss variants (plain vs label-smoothed).

## Core ideas

For true next token y and predicted distribution p:

    L = -log p(y)

Average over tokens. That is it. Cross-entropy asks: how surprised
was the model by the actual next token? Confident and right -> loss
near 0. Confident and wrong -> large loss. The gradient pushes
probability mass toward the true token, proportionally to how wrong
the model was.

Why this loss and not mean-squared error on logits: cross-entropy is
the maximum-likelihood objective for categorical outcomes. Minimizing
it is exactly maximizing the probability the model assigns to real
text. Perplexity is just exp(loss) - "the model is as confused as if
choosing uniformly among PPL options per token."

Numerically, never compute softmax then log. Use the log-sum-exp
trick (log_softmax): L = -logit_y + log(sum(exp(logits))). Stable in
fp16 where naive softmax overflows.

## Gotchas

- Loss is averaged over *unmasked* tokens only - PAD must be excluded
  or it pollutes the number.
- A loss of 0 is not the goal; on real text it means memorization.
- Comparing losses across tokenizers is meaningless - different
  tokenizations, different per-token surprise.

## Quick reference

- L = -mean(log p(true token)) over non-pad tokens. PPL = e^L.
  Implement via log_softmax, never softmax-then-log.
