---
skill_id: sys_python_itertools_functools
name: Python itertools and functools
description: Composable iteration primitives and higher-order function tools.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python itertools and functools

## Purpose

Composable iteration primitives and higher-order function tools.

## Overview

itertools provides lazy, composable iteration building blocks. chain flattens several iterables into one stream; islice takes a slice of any iterator without materializing it; groupby clusters consecutive equal keys (sort first if you want global groups); product/permutations/combinations generate combinatorial sequences; count/cycle/repeat build infinite iterators for controlled consumption with islice or zip. accumulate runs a running reduction - prefix sums in one call. The power is composition: small lazy pieces chained into pipelines that use constant memory. functools covers higher-order function utilities: reduce folds an iterable with a binary function; lru_cache memoizes pure functions (hashable args required); partial freezes some arguments of a function, creating specialized versions; wraps preserves metadata in decorators; total_ordering fills in comparison methods from __eq__ plus one ordering method. Together they push code toward declarative pipelines: describe the data flow, not the loop mechanics. Caution: infinite iterators must always be bounded by islice or a consuming loop with a break, or the program hangs consuming forever.

## Quick reference

- chain: flatten iterables. islice: lazy slice of any iterator.

- groupby: clusters CONSECUTIVE equal keys - sort first for global groups.

- product/permutations/combinations: combinatorial generation.

- count/cycle/repeat: infinite iterators - always bound them.

- functools.reduce: fold. lru_cache: memoize. partial: freeze arguments.

- Compose lazily; materialize only at the end if needed.


## Worked example

Lazy pipeline: count, islice, accumulate:

```
import itertools, functools, operator

naturals = itertools.count(1)
first_ten = list(itertools.islice(naturals, 10))
running = list(itertools.accumulate(first_ten))
print(first_ten)
print(running)

double = functools.partial(operator.mul, 2)
print(double(21))
```

- count(1) is infinite; islice bounds it to 10 items.

- accumulate defaults to addition: running totals.

- partial(operator.mul, 2) freezes the first argument.


## Common mistakes

- Consuming an infinite itertools iterator without a bound.
  Fix: Always pair count/cycle/repeat with islice or an explicit break.

- Using reduce where sum()/any()/a comprehension reads better.
  Fix: reduce is for genuinely custom folds; builtins cover the common ones.


## Quick checks

Q: Why did groupby give me several groups for the same key?
A: groupby only clusters consecutive equal keys. If equal keys are scattered, you get one group per run. Sort by the key first when you want global groups.


Q: When is lru_cache unsafe?
A: When the function has side effects, depends on mutable/global state, or takes unhashable arguments. It is for pure functions with hashable inputs.


## Mental model

itertools pieces are plumbing fittings: each does one simple thing to a stream (join pipes, add a valve, split flow), and you thread them together into a pipeline. functools tools are jigs for the workshop - partial clamps a setting in place, lru_cache remembers measurements so you never re-measure.
