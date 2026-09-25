---
skill_id: sys_python_collections_module
name: Python collections Module
description: Counter, defaultdict, deque, namedtuple: the stdlib's specialized containers.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python collections Module

## Purpose

Counter, defaultdict, deque, namedtuple: the stdlib's specialized containers.

## Overview

The collections module holds containers for patterns the builtins cover awkwardly. Counter tallies hashables: Counter(words) gives frequencies, .most_common(n) ranks them - one line for histogram tasks. defaultdict auto-creates missing entries via a factory, cleaning up grouping and accumulation loops. deque is a double-ended queue with O(1) appends and pops on both ends, plus maxlen for fixed-size sliding windows; it beats list for queue workloads where pop(0) would be O(n). namedtuple builds lightweight immutable records with named fields - readable, tuple-compatible, and cheap. OrderedDict is mostly legacy now that dict preserves order; ChainMap layers mappings so lookups fall through (useful for config: CLI over env over defaults). Practical guidance: reach for Counter before hand-rolling counts, deque before list-as-queue, and defaultdict before setdefault chains. These are not exotic - they are the idiomatic answers to extremely common shapes, and using them signals fluency to readers.

## Quick reference

- Counter: frequency tallies; .most_common(n) ranks them.

- defaultdict(factory): auto-creates missing keys (list, int, set).

- deque: O(1) append/pop on both ends; maxlen gives sliding windows.

- namedtuple: tiny immutable record with named fields.

- ChainMap: layered lookups across several mappings (config precedence).

- Prefer these over hand-rolled equivalents: clearer and faster.


## Worked example

Counter, deque window, and namedtuple:

```
from collections import Counter, deque, namedtuple

votes = ['a', 'b', 'a', 'c', 'a', 'b']
print(Counter(votes).most_common(2))

window = deque(maxlen=3)
for n in range(5):
    window.append(n)
print(list(window))          # [2, 3, 4]

Point = namedtuple('Point', 'x y')
p = Point(1, 2)
print(p.x, p[0])
```

- most_common returns (element, count) pairs in rank order.

- maxlen=3 silently discards the oldest item on overflow.

- namedtuple fields work by name and by index.


## Common mistakes

- Using list as a queue with pop(0) in a hot loop.
  Fix: Switch to collections.deque for O(1) popleft().

- Forgetting maxlen on deque when a bounded window was intended.
  Fix: Pass maxlen= at construction; it enforces the bound automatically.


## Quick checks

Q: Why is deque better than a list for queues?
A: list.pop(0) shifts every remaining element: O(n). deque is a linked block structure with O(1) operations on both ends. For FIFO workloads the difference shows up fast at scale.


Q: Counter vs manual dict counting?
A: Counter(words) replaces the loop entirely, and most_common, subtraction, and intersection come free. Manual counting is only needed for exotic weighting.


## Mental model

Counter is a tally sheet that counts itself; deque is a conveyor belt you can load and unload from either end; namedtuple is a labeled index card instead of a scrap of paper with two numbers on it.
