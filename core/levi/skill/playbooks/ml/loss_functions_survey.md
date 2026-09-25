---
skill_id: ml_loss_functions_survey
name: Loss Functions Survey: MSE, MAE, Hinge, CTC
description: The standard losses outside language modeling, when each is right, and how their gradients behave.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Loss Functions Survey: MSE, MAE, Hinge, CTC

## Purpose

Survey the losses you reach for when the task is not next-token
prediction: regression, robust regression, classification margins,
and sequence alignment.

## When to use

- Picking a loss for a non-LM head (regression probe, classifier).
- Understanding why MSE punishes outliers so hard.
- Reading speech/handwriting literature (CTC).

## Core ideas

- **MSE** (mean squared error): mean((y - y_hat)^2). Gradient scales
  with the error - big mistakes shout. Standard for regression, but
  outlier-sensitive: one bad label dominates the batch.
- **MAE** (mean absolute error): mean(|y - y_hat|). Constant-magnitude
  gradients - robust to outliers, but non-differentiable at 0 and
  slower to converge precisely.
- **Huber:** quadratic near 0, linear far away - MSE's precision with
  MAE's robustness. The default sane choice for noisy regression.
- **Hinge:** max(0, 1 - y*y_hat) for y in {-1, +1}. Only cares about
  margin violations; the SVM classic. Rare in deep learning now.
- **CTC:** for unsegmented sequences (speech): sums over all
  alignments of output to input, inserting blanks. Lets you train
  sequence models without frame-level labels.

## Gotchas

- Loss choice is a statement about your noise model: MSE assumes
  Gaussian noise, MAE Laplacian. Pick the one matching your data.
- Scale matters: MSE on unnormalized targets (house prices in
  dollars) gives absurd gradient magnitudes - normalize first.
- CTC needs the blank token and collapses repeats; decoding needs a
  beam search or greedy collapse pass.

## Quick reference

- Regression: Huber default. Classification: cross-entropy. Margin:
  hinge. Unsegmented sequences: CTC.
