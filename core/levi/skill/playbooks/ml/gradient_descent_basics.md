---
skill_id: ml_gradient_descent_basics
name: Gradient Descent: the Core Loop
description: The update rule everything else elaborates: follow the downhill slope of the loss, one step at a time.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Gradient Descent: the Core Loop

## Purpose

State the fundamental optimization loop plainly - compute gradients,
step against them - so every fancier optimizer reads as a modification
of this one idea.

## When to use

- First-principles grounding before Adam/SGD variants.
- Debugging "loss not decreasing" (check this loop first).
- Teaching how neural networks actually learn.

## Core ideas

    theta = theta - lr * grad(loss, theta)

Repeat. The gradient points uphill (direction of steepest increase);
stepping against it descends. The learning rate lr sets step size:
too small and training crawls; too large and it diverges, oscillating
or exploding across the loss valley.

Full-batch gradient descent computes grad over the entire dataset per
step - exact but impossibly slow at scale. Everything practical uses
stochastic estimates (minibatches), trading exactness for speed: the
noise turns out to help escape sharp minima, and 1000 noisy steps beat
1 exact step per unit of compute.

The loss landscape of deep nets is non-convex - no global-optimality
guarantees. What saves us: overparameterized nets have many good-enough
minima, and gradient descent with noise finds flat ones that
generalize.

## Gotchas

- "Loss not moving" checklist: lr absurd (1e-7 or 1.0), gradients not
  flowing (check a histogram), loss computed wrong (PAD unmasked).
- Gradient descent minimizes the *training* loss. Generalization comes
  from the implicit regularization of SGD noise + explicit
  regularization - not from the update rule alone.
- Shuffling matters: correlated batches (all one class) make the
  stochastic gradient a biased walk.

## Quick reference

- theta -= lr * grad. Minibatches for speed; noise helps. Tune lr
  first - it dominates everything else.
