---
skill_id: ml_label_smoothing
name: Label Smoothing
description: Softening hard targets to curb overconfidence: how it changes gradients and when it helps calibration.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Label Smoothing

## Purpose

Explain label smoothing: replace the one-hot target with a mix of the
true class and uniform noise, and show why slightly-less-certain
models generalize and calibrate better.

## When to use

- Classification or LM training with overconfident predictions.
- Improving calibration (predicted probabilities matching reality).
- Understanding a cross-entropy variant in a recipe.

## Core ideas

Hard target: probability 1 on the true token. Smoothed (eps=0.1):

    p_true = 1 - eps + eps/V
    p_other = eps/V   for every other token

The model is penalized for driving the true logit to infinity - the
loss never reaches zero, so weights stay bounded and the model stays
less cocksure. Gradients push *away* from the wrong tokens only
mildly (eps/V each) instead of demanding absolute certainty on the
right one.

Effect on calibration: models trained with smoothing output
probabilities closer to true frequencies - useful when downstream
decisions use the probabilities (beam search scores, abstention
thresholds).

## Gotchas

- Smoothing changes the optimal solution: the model can never reach
  zero loss. Don't compare smoothed vs unsmoothed losses directly.
- For knowledge-distillation teachers, smoothing can *hurt* - the
  student learns from the teacher's soft targets already.
- eps=0.1 is standard; larger values visibly degrade top-1 accuracy
  while improving calibration - know which you need.

## Quick reference

- Target = (1-eps) on true + eps/V everywhere. Curbs overconfidence,
  aids calibration, loss never hits zero.
