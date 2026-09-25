---
skill_id: sys_algo_binary_search
name: Algorithm Binary Search
description: Halving the search space: the pattern behind O(log n) lookup.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, cs]
version: 1.0.0
---
# Algorithm Binary Search

## Purpose

Halving the search space: the pattern behind O(log n) lookup.

## Overview

Binary search finds a target in sorted data in O(log n) by halving the candidate range each step: compare the middle, discard the half that cannot contain the target, repeat. The loop invariant - 'the target, if present, is within [lo, hi]' - is what makes it correct; most bugs are boundary errors that break it. Write it with lo <= hi and mid = (lo + hi) // 2, moving lo = mid + 1 or hi = mid - 1 past the checked element so the range strictly shrinks. The pattern generalizes beyond exact search: bisect_left/right find insertion points, and 'binary search on the answer' solves optimization problems with a monotonic predicate (is x feasible?) - e.g., minimum capacity to ship in D days. Preconditions are everything: the data must be sorted (or the predicate monotonic); on unsorted data it silently returns wrong answers. Python's bisect module implements the insertion-point variants on lists - use it instead of hand-rolling. Complexity: O(log n) comparisons, O(1) space iteratively; recursion adds O(log n) stack.

## Quick reference

- Halve [lo, hi] each step; invariant: target (if any) is inside.

- Move past mid (lo = mid+1 / hi = mid-1) so the range strictly shrinks.

- bisect_left/right: insertion points in sorted lists - use the module.

- Generalizes: binary-search a monotonic predicate ('binary search on answer').

- Requires sorted data; on unsorted input it fails silently.

- O(log n) time, O(1) space iterative.


## Worked example

Binary search and binary-search-on-answer:

```
import bisect

def binary_search(a, target):
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == target:
            return mid
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

grades = [55, 61, 70, 88, 92]
i = bisect.bisect_left(grades, 70)   # insertion point keeps sorted order
print(i, binary_search(grades, 88))
```

- lo <= hi with mid excluded each step: terminates, no infinite loop.

- bisect_left returns where 70 belongs: the module version of the pattern.

- Off-by-one errors live here: test empty, single, missing, and boundary inputs.


## Common mistakes

- Infinite loop from lo = mid instead of mid + 1.
  Fix: Always exclude the checked mid so the interval strictly shrinks.

- Searching unsorted data and trusting the result.
  Fix: Assert sortedness or sort first; binary search fails silently otherwise.


## Quick checks

Q: When is binary search the wrong tool?
A: Unsorted data (sort first only if you search repeatedly - one search does not amortize O(n log n) sort), tiny n where linear scan's constants win, or non-random-access structures like linked lists.


Q: What is 'binary search on the answer'?
A: For optimization with a monotonic predicate (if capacity C works, any larger C works), binary-search the smallest feasible C instead of the data itself. Turns O(n) feasibility checks into O(n log range).


## Mental model

Binary search is the 'hot or cold' number game played optimally: each guess ('higher'/'lower') eliminates half the possibilities. Bisect is the librarian who, given a sorted shelf, tells you exactly which gap your new book slides into.
