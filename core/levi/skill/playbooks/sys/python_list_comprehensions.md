---
skill_id: sys_python_list_comprehensions
name: Python Comprehensions
description: List, dict, and set comprehensions: building collections declaratively in one expression.
risk: info
permissions: []
requires_confirmation: false
tags: [python, idiom]
version: 1.0.0
---
# Python Comprehensions

## Purpose

List, dict, and set comprehensions: building collections declaratively in one expression.

## Overview

A comprehension builds a collection from an iterable in a single expression: [expr for x in items if cond]. Read it inside out: the for walks the source, the optional if filters, and the leading expression transforms. List comprehensions replace the common append-in-a-loop pattern with something shorter and faster - the loop runs in C rather than as Python bytecode. Dict comprehensions use {key_expr: val_expr for ...} and set comprehensions {expr for ...}; generator expressions (expr for x in items) are the lazy cousin, producing values on demand instead of materializing a list, which matters for large or infinite streams. Comprehensions have their own scope for the loop variable, so they do not leak names the way a manual loop does. The readability limit is real: one for plus one if stays clear, but nested comprehensions with multiple fors and conditions turn into puzzles - at that point write the explicit loop. Use comprehensions for transform-and-filter; use a plain loop when the body has side effects like printing, appending to several places, or complex branching. A neat trick: any() and all() pair with generator expressions for readable existence checks without building a temporary list.

## Quick reference

- [f(x) for x in items if cond]: transform + filter in one expression.

- {k: v for ...}: dict comprehension. {f(x) for ...}: set comprehension.

- (f(x) for x in items): generator expression - lazy, memory-light.

- any()/all() with a genexpr: readable existence checks, short-circuiting.

- Comprehension loop variables do not leak into the enclosing scope.

- One for + one if is the readability ceiling; beyond that, write the loop.

- Never use a comprehension purely for side effects; use a for loop.


## Worked example

Transform, filter, and lazy pipelines:

```
nums = range(20)
evens_squared = [n * n for n in nums if n % 2 == 0]

word = 'banana'
letter_counts = {ch: word.count(ch) for ch in set(word)}

total = sum(n * n for n in nums if n % 2 == 0)  # genexpr: no temp list

has_big = any(n > 15 for n in nums)
print(evens_squared[:5], letter_counts, total, has_big)
```

- The if filters before the expression transforms.

- sum() over a generator expression avoids building an intermediate list.

- any() short-circuits: it stops at the first True.


## Common mistakes

- Writing a triply-nested comprehension that nobody can read.
  Fix: Extract the inner logic into a helper function, then comprehend over it.

- [print(x) for x in items] - a list of Nones built for side effects.
  Fix: Use a plain for loop when the point is the side effect.


## Quick checks

Q: Are comprehensions actually faster than loops?
A: Usually yes for simple cases: the iteration happens in C and avoids repeated method lookups like append. The bigger win is readability for the simple cases; for complex logic the explicit loop is both clearer and fine.


Q: List comprehension or generator expression - how do I choose?
A: Need the whole result at once, indexed or reused? List. Streaming through data once, especially large data? Generator expression - constant memory.


## Mental model

A comprehension is a factory line: raw items roll in on the belt (for), defective ones get kicked off (if), and each survivor gets stamped (expression). A generator expression is the same line with no warehouse - each finished item ships immediately instead of piling up.
