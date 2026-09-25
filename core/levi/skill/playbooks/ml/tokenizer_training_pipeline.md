---
skill_id: ml_tokenizer_training_pipeline
name: Tokenizer Training Pipeline
description: The practical steps from raw corpus to a working tokenizer.json: sampling, pre-tokenization, vocab sizing.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Tokenizer Training Pipeline

## Purpose

Give the concrete pipeline for training a BPE tokenizer on your own
corpus: what to feed it, which knobs matter, and how to validate the
result before a model ever sees it.

## When to use

- Training the tokenizer for LEVI's brain or any new model.
- Diagnosing why a model wastes tokens on your domain text.
- Reproducing a tokenizer.json from scratch.

## Core ideas

1. **Sample the corpus.** Train on a representative sample (a few GB
   is plenty); oversample the domains you care about. The tokenizer
   learns frequencies - feed it what the model will read.
2. **Pre-tokenization.** Decide the regex that splits text before BPE
   (GPT-2 style: contractions, words, numbers, whitespace runs). This
   bounds how merges can cross boundaries.
3. **Vocab size.** 8k-32k for small models, 32k-128k for large. LEVI's
   v2 brain uses 8192: matched to model scale (13.8M params) so the
   embedding table (~3.1M params tied) stays proportional.
4. **Special tokens.** Add BOS/EOS/PAD/UNK after training; reserve ids.
5. **Validate.** Check fertility (tokens per word) on domain samples,
   round-trip decode fidelity, and that no training-domain text
   degrades into byte soup.

```python
# pseudocode with a BPE trainer
tok = BPETrainer(vocab_size=8192, min_frequency=2,
                 special_tokens=["<bos>", "<eos>", "<pad>"])
tok.train_from_iterator(corpus_sample)
tok.save("tokenizer.json")
assert tok.decode(tok.encode(s)) == s  # round-trip check
```

## Gotchas

- min_frequency too low admits junk merges from typos; too high starves
  small-but-real morphemes.
- Train the tokenizer on the *training* distribution, not the eval
  set - but do check eval fertility afterward.
- Changing pre-tokenization later = new tokenizer = retrain the model.

## Quick reference

- Sample representatively -> pre-tokenize -> pick vocab size ->
  special tokens -> validate fertility + round-trip.
