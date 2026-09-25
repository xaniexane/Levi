---
skill_id: ml_tokenizer_roundtrip_gotchas
name: Tokenizer Round-Trip Gotchas
description: Why encode(decode(x)) is not always x: leading spaces, byte fallbacks, and normalization traps.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, tokenization]
version: 1.0.0
---
# Tokenizer Round-Trip Gotchas

## Purpose

Catalog the ways tokenizers silently mangle text: leading-space
conventions, Unicode normalization, byte-fallback decoding, and why
your eval harness must test round-trips instead of assuming them.

## When to use

- Building eval or data pipelines that decode model output.
- Debugging "the model said X but the log shows Y".
- Comparing outputs across different tokenizers.

## Core ideas

The contract you want: decode(encode(s)) == s for all s. It breaks in
practice:

- **Leading spaces:** many BPE schemes encode " hello" as one token
  ("_hello") but a bare "hello" at string start differently. Prompt
  formatting ("Q:" vs " Q:") changes tokenization.
- **Normalization:** some tokenizers lowercase or NFKC-normalize before
  encoding - decode can never recover the original.
- **Byte fallback:** undecodable bytes decode to replacement
  characters; the round trip is lossy by design there.
- **Special tokens in text:** a literal "<eos>" in user input may be
  parsed as the control token, truncating the sequence.

Test the contract explicitly on your actual data distribution,
including edge cases (empty string, lone spaces, emoji, mixed
scripts).

## Gotchas

- Eval metrics computed on decoded text inherit tokenizer quirks -
  compare like with like.
- Streaming decode (token by token) can show partial UTF-8 bytes as
  garbage mid-sequence; buffer until character boundaries.
- Never hand-edit token id sequences without checking what the
  specials map to in *this* tokenizer.

## Quick reference

- Assert decode(encode(s)) == s on real data. Watch: leading spaces,
  normalization, byte fallback, literal special-token strings.
