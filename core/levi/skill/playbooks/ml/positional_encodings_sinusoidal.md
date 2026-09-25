---
skill_id: ml_positional_encodings_sinusoidal
name: Sinusoidal Positional Encodings
description: The original fixed position scheme: sine/cosine waves at many frequencies, and why it generalizes.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Sinusoidal Positional Encodings

## Purpose

Explain the original transformer's fixed positional encoding: adding
sine and cosine waves of geometrically spaced frequencies to each
position, and why this lets the model reason about relative distance.

## When to use

- Understanding the 2017 baseline before learned/RoPE alternatives.
- Debugging order-sensitivity in a model without learned positions.
- Teaching how position can be injected without parameters.

## Core ideas

For position pos and dimension i:

    PE(pos, 2i)   = sin(pos / 10000^(2i/d))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d))

Low dimensions oscillate fast (fine position detail), high dimensions
oscillate slowly (coarse region). The neat property: PE(pos+k) is a
*linear function* of PE(pos), so the model can learn to attend by
relative offset using linear projections alone. No parameters, works
for sequences longer than any seen in training - though quality
degrades as wavelengths run out.

## Gotchas

- Fixed encodings cannot adapt: if your task needs position 5000 to
  mean something special, sinusoids will not learn it.
- The 10000 base is a hyperparameter in disguise; longer contexts want
  larger bases so slow waves stay slow.
- Modern models mostly replaced this with learned positions or RoPE,
  but the "relative offset is linear" insight is what RoPE builds on.

## Quick reference

- PE added to token embeddings before the first block.
- Frequencies span 2*pi to 2*pi/10000 across dimensions.
