---
skill_id: ml_levi_tokenizer_stack
name: LEVI Tokenizer Stack
description: The actual tokenizer artifacts in core/levi/brain: tokenizer.json, the BPE lineage, and the training spec.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI Tokenizer Stack

## Purpose

Map LEVI's real tokenizer artifacts - which files exist, what each
one is for, and the contracts between tokenizer and model - from
direct inspection of core/levi/brain/.

## When to use

- Training or continuing any brain model (tokenizer must match).
- Debugging encode/decode mismatches.
- Extending the tokenizer (BPE rounds).

## Core ideas

What exists (verified on disk):

- `train/tokenizer.json` - the working tokenizer, vocab_size 8192
  (byte-level BPE). The v2 harness resolves the tokenizer through
  `build_tokenizer()` and *refuses loudly* on vocab mismatch before
  torch ever sees it.
- `train/tokenizer_spec.json` - the training spec: source corpus
  (corpus.jsonl), text field, vocab_size 8192, max_train_chars
  2,000,000, force_retrain flag.
- `tokenizers/levi-bpe-v2/` - the versioned v2 BPE tokenizer lineage.
- `train/weights/bpe_round3/` - artifacts from BPE training round 3.
- Builders: `train_bpev3.py`, `continue_bpe.py` - training and
  continuing BPE rounds.

Contracts: model config vocab_size must equal the resolved
tokenizer's vocab size (harness-enforced). Special-token ids live in
the tokenizer config - read them, don't assume. The stage-1 brain
(train.py) is character-level and doesn't use this stack; v2 does.

## Gotchas

- Swapping in a retrained tokenizer without retraining the model
  silently breaks every id mapping - the harness guard exists
  because this mistake is catastrophic and quiet.
- max_train_chars 2M bounds tokenizer training cost; the tokenizer
  learns frequencies, so the 2M chars must represent the target
  distribution.
- Byte-level BPE means no UNK path - but verify byte-fallback
  round-trips on your data anyway.

## Quick reference

- Working: train/tokenizer.json (8192, byte-BPE). Spec:
  tokenizer_spec.json. Lineage: tokenizers/levi-bpe-v2,
  weights/bpe_round3. Harness enforces vocab match.
