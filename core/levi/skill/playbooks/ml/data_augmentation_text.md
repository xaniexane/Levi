---
skill_id: ml_data_augmentation_text
name: Data Augmentation for Text
description: Creating training variety without new data: paraphrase, back-translation, and what augmentation can't fix.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# Data Augmentation for Text

## Purpose

Explain text augmentation honestly: the techniques that manufacture
training variety (paraphrase, back-translation, noise), where they
help, and their hard limits compared to real data.

## When to use

- Small-data fine-tuning that overfits.
- Low-resource languages or narrow domains.
- Deciding whether to augment or go collect data.

## Core ideas

- **Paraphrasing:** rewrite examples preserving meaning (rule-based
  or model-based). Teaches invariance to phrasing.
- **Back-translation:** translate to another language and back; the
  round trip produces natural paraphrases with human-like noise.
- **Noise injection:** typos, case changes, punctuation drops -
  robustness to messy inputs (the classic, and genuinely useful for
  user-facing models).
- **Template expansion:** slot-fill templates ("The {animal} sat on
  the {object}") for structured domains. High volume, low diversity
  per example - good for format learning, weak for knowledge.

What augmentation can't do: create *new information*. Augmented data
teaches robustness and format, not facts. A model augmented 10x on a
small knowledge base knows the same facts, phrased ten ways.

## Gotchas

- Model-generated paraphrases inherit the generator's biases and
  errors - augmentation can launder hallucinations into "training
  data". Verify samples.
- Too much augmentation shifts the distribution: the model learns
  augmented-text style, not real-text style. Cap the ratio.
- For pre-training at scale, augmentation is mostly pointless - the
  web already contains the variation.

## Quick reference

- Augment for robustness/format, not knowledge. Verify generated
  paraphrases. Cap the augmented fraction; real data still wins.
