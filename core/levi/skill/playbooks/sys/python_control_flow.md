---
skill_id: sys_python_control_flow
name: Python Control Flow
description: if/elif/else, for and while loops, and the loop-control tools that keep programs readable.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Control Flow

## Purpose

if/elif/else, for and while loops, and the loop-control tools that keep programs readable.

## Overview

Control flow is how a program decides what runs next. Python's if/elif/else chain tests conditions top to bottom and runs the first true branch; an optional else catches everything left over. Conditions use truthiness: empty collections, zero, None, and False are falsy, everything else is truthy. Prefer direct truthiness tests (`if items:`) over comparing to empty values. The for loop iterates over any iterable - lists, strings, dicts, generators - and the loop variable takes each element in turn. Use enumerate() when you need the index and zip() to walk two sequences together; both are clearer than manual indexing. The while loop repeats until its condition turns false and fits problems where the stop rule is a state, not a count: reading until EOF, retrying until success. break exits a loop immediately, continue skips to the next iteration, and the rarely used loop-else runs only when the loop finished without break - a clean way to express search-then-not-found. Guard clauses (early returns for the uninteresting cases) flatten nesting and make the main path read top to bottom. Match statements (Python 3.10+) give structural pattern matching for dispatching on shape, but a plain if-chain is fine for simple value tests. The rule of thumb: the shape of the loop should mirror the shape of the problem.

## Quick reference

- if/elif/else: first true branch wins; else is optional.

- Falsy: None, False, 0, 0.0, '', [], {}, set(). Everything else is truthy.

- for x in iterable: the Pythonic loop. enumerate() for index, zip() for pairs.

- while cond: repeats while true; make sure the condition can become false.

- break: exit loop now. continue: skip to next iteration. loop-else: runs if no break.

- Guard clauses: return early for edge cases to avoid deep nesting.

- match/case (3.10+): structural pattern matching for shape-based dispatch.


## Worked example

Loop idioms: enumerate, zip, and loop-else:

```
scores = [88, 42, 95, 71]

for i, s in enumerate(scores):
    print(i, s)

names = ['amy', 'bo', 'cy']
for name, s in zip(names, scores):
    print(name, '->', s)

def find_first_even(nums):
    for n in nums:
        if n % 2 == 0:
            return n
    return None          # loop-else equivalent via early return
```

- enumerate yields (index, value) pairs starting at 0.

- zip stops at the shorter sequence; use itertools.zip_longest to pad.

- Early return is usually clearer than a for/else construct.


## Common mistakes

- Modifying the loop variable expecting it to change the list: `for x in xs: x = f(x)` rebinds x, not the slot. Assign by index or build a new list.
  Fix: Use enumerate for index assignment, or a comprehension to rebuild.

- while True with no reachable break - an accidental infinite loop.
  Fix: Make the exit condition obvious and test it with a bounded input first.


## Quick checks

Q: When should I use while instead of for?
A: Use for when you iterate a known collection or a fixed range. Use while when the termination depends on evolving state - waiting for input, draining a queue, retrying an operation - where there is no iterable to walk.


Q: What does for/else actually do?
A: The else block runs when the loop completes normally, i.e. without hitting break. It is meant for search loops: break when found, else report not found. Many teams prefer an early return instead for readability.


## Mental model

A for loop is a conveyor belt: every item passes the station exactly once and you never worry about the belt stopping. A while loop is a bouncer checking IDs at the door: the line keeps moving only while the condition holds, and if the bouncer falls asleep (condition never changes) the line never ends.
