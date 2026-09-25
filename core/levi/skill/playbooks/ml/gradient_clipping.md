---
skill_id: ml_gradient_clipping
name: Gradient Clipping
description: Capping gradient norms to survive loss spikes: global norm clipping, when it triggers, and what it hides.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training, optimization]
version: 1.0.0
---
# Gradient Clipping

## Purpose

Explain global gradient-norm clipping - rescale the gradient when its
norm exceeds a threshold - as cheap insurance against exploding
updates, and note what frequent clipping is telling you.

## When to use

- Any RNN/transformer training (standard practice).
- A run that intermittently NaNs or spikes.
- Deciding the clip threshold.

## Core ideas

    if ||g|| > c: g = g * (c / ||g||)

Direction preserved, magnitude capped at c (typically 1.0). This
bounds the worst single update: one bad batch (mislabeled example,
numerical glitch, pathological sequence) cannot undo hours of
training. With Adam the need is smaller than with SGD - adaptivity
already normalizes per-parameter - but spikes still occur (loss
spikes correlate with gradient-norm spikes), so clipping stays on.

What frequent clipping means: if the clip triggers on most steps,
your effective learning rate is being set by c, not by lr - the
threshold has become the schedule. Either the lr is too high or the
data has systematic pathologies (check for them; don't just raise c).

## Gotchas

- Clip *after* unscaling in mixed precision (unscale first, then
  clip, then step) - order matters.
- Per-parameter clipping exists but global-norm is the standard; it
  preserves the update direction.
- Clipping hides the symptom (explosion) not the cause (bad batch,
  bug). Investigate chronic clipping.

## Quick reference

- g *= min(1, c/||g||), c ~ 1.0. Insurance against spikes; chronic
  clipping means lr too high or data pathology.
