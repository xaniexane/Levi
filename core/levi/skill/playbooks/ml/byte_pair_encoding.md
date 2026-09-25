---
skill_id: ml_byte_pair_encoding
name: Byte-Pair Encoding (BPE)
description: How BPE builds a subword vocabulary by repeatedly merging the most frequent adjacent pair.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Byte-Pair Encoding (BPE)

## Purpose

Explain byte-pair encoding end to end: the merge-learning loop that
builds a subword vocabulary from raw text, how encoding applies the
learned merges greedily, and why subwords beat both words and
characters for language models.

## When to use

- Training a tokenizer for a new model or corpus.
- Understanding why "tokenizer.json" contains a merges list.
- Debugging weird token splits (e.g. a common word split oddly).

## Core ideas

Start with a base vocabulary of individual bytes (256 entries - every
input is representable, no UNK needed). Then repeat: count all adjacent
symbol pairs in the training corpus, merge the most frequent pair into
a new symbol, add it to the vocabulary. After N merges you have a vocab
of 256 + N entries, from single bytes up to whole common words.

Encoding applies the merges in the learned order, greedily: "the" in
English quickly becomes one token because t+h, th+e merged early and
often. Rare words fall back to smaller pieces or bytes - nothing is
ever unrepresentable.

```python
# learning loop, sketch
vocab = {bytes([b]) for b in range(256)}
merges = []
for _ in range(num_merges):
    pairs = count_adjacent_pairs(corpus, vocab)
    best = max(pairs, key=pairs.get)
    merges.append(best)
    vocab.add(best[0] + best[1])   # new merged symbol
```

## Gotchas

- BPE is greedy, not optimal: the merge order learned on the training
  corpus can split a word in a linguistically silly way. It optimizes
  frequency, not meaning.
- Whitespace handling matters: most BPE variants treat space as part of
  the following token ("_the"), which affects leading-space behavior at
  generation start.
- A tokenizer trained on English-heavy data tokenizes other languages
  into many tiny pieces - fertility (tokens per word) explodes, which
  wastes context and compute.

## Quick reference

- Base: 256 byte tokens. Learn: N most-frequent-pair merges.
- Encode: apply merges greedily in learned order. Never UNK with byte
  fallback.
