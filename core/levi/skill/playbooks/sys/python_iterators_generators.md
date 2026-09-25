---
skill_id: sys_python_iterators_generators
name: Python Iterators and Generators
description: The iterator protocol, generator functions, and lazy evaluation for memory-light pipelines.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Iterators and Generators

## Purpose

The iterator protocol, generator functions, and lazy evaluation for memory-light pipelines.

## Overview

Iteration in Python runs on a protocol: an iterable has __iter__ returning an iterator, and an iterator has __next__ raising StopIteration when exhausted. for loops, unpacking, and comprehensions all consume this protocol, which is why custom classes become loopable by implementing two methods. Generator functions make writing iterators trivial: any function containing yield returns a generator object that pauses at each yield and resumes on the next request, keeping its local state between calls. This laziness is the point - a generator over a 10 GB log file uses constant memory because values are produced one at a time and discarded after use. yield from delegates to a sub-generator, flattening nested iteration. Generator expressions give the same laziness inline. The trade-off: iterators are single-pass and stateful. Once consumed, a generator is empty; tee() or re-creation is needed for a second pass. Mixing eager lists and lazy generators in one pipeline is normal: generate lazily, materialize only at the boundary where you need random access or reuse. itertools builds on this foundation with composable primitives - chain, islice, groupby - that turn iteration into a toolkit rather than a chore.

## Quick reference

- Iterable: has __iter__. Iterator: has __next__, raises StopIteration at end.

- yield turns a function into a generator factory; state persists between yields.

- Generators are lazy and single-pass: consumed once, then empty.

- yield from delegates iteration to a sub-iterable.

- itertools: chain, islice, groupby, accumulate - composable iteration tools.

- Generate lazily, materialize (list()) only where random access or reuse is needed.


## Worked example

A lazy pipeline over a large stream:

```
def read_batches(path, size=1000):
    batch = []
    with open(path) as f:
        for line in f:
            batch.append(line.rstrip('\n'))
            if len(batch) == size:
                yield batch
                batch = []
    if batch:
        yield batch

def errors_only(batches):
    for batch in batches:
        yield from (l for l in batch if 'ERROR' in l)
```

- Each yield pauses the function; locals (batch) survive between calls.

- Memory stays flat: only one batch exists at a time.

- yield from with a genexpr flattens filtering into the pipeline.


## Common mistakes

- Returning a list from a 'streaming' helper, blowing memory on big inputs.
  Fix: yield items one at a time; let the caller decide whether to materialize.

- Reusing a consumed generator and getting silent empty results.
  Fix: Treat generators as disposable; create a new one per pass.


## Quick checks

Q: Why is my generator empty the second time I loop over it?
A: Generators are single-pass iterators. The first loop consumed it; the second sees StopIteration immediately. Call the generator function again for a fresh one, or materialize with list() if you need multiple passes.


Q: Generator function vs generator expression - which to pick?
A: Expression for a one-line transform/filter inline. Function when you need statements: setup, try/finally cleanup, or multi-stage logic.


## Mental model

A generator is a vending machine that makes each snack fresh when you press the button, instead of a warehouse stocked with every snack ever. Press again, get the next one. But once the machine is empty, pressing does nothing - you need a restock (a new generator).
