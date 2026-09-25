---
skill_id: sys_algo_sorting
name: Algorithm Sorting
description: The essential sorts: how they work, when each wins, and stability.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, cs]
version: 1.0.0
---
# Algorithm Sorting

## Purpose

The essential sorts: how they work, when each wins, and stability.

## Overview

Sorting is the most-studied algorithm family. Quicksort: pick a pivot, partition smaller/larger, recurse - O(n log n) average, O(n^2) worst, in-place, but not stable. Mergesort: split in half, sort, merge - O(n log n) guaranteed, stable, needs O(n) extra space. Heapsort: O(n log n) worst-case in-place but not stable and cache-unfriendly. Insertion sort: O(n^2) worst but O(n) on nearly-sorted data with tiny constants - why libraries use it for small subarrays. Timsort (Python's sorted): hybrid merge/insertion exploiting real-world runs - stable, O(n log n) worst, adaptive to O(n) on sorted input. Counting/radix sorts beat n log n for bounded integer keys by sorting on digits. Stability (equal elements keep order) matters when sorting by multiple keys in passes. Practical rule: use the language's sort (timsort in Python) unless you have a proven reason - it is battle-tested and adaptive. Write custom sorts only for exotic keys, external memory, or learning. Key insight for interviews: most 'clever' problems reduce to sort + one linear pass.

## Quick reference

- Quicksort: n log n avg, in-place, unstable. Mergesort: n log n, stable, O(n) space.

- Timsort (Python sorted): stable, adaptive, the default choice.

- Insertion sort: O(n) on nearly-sorted data; used for small subarrays.

- Counting/radix: beat n log n for bounded integer keys.

- Stable = equal elements keep original order (matters for multi-key sorts).

- Default to the stdlib sort; custom sorts need a proven reason.


## Worked example

Sort + one linear pass solves many problems:

```
def two_sum_sorted(nums, target):
    nums = sorted(nums)          # timsort: O(n log n)
    lo, hi = 0, len(nums) - 1
    while lo < hi:               # one linear pass: O(n)
        s = nums[lo] + nums[hi]
        if s == target:
            return nums[lo], nums[hi]
        if s < target:
            lo += 1
        else:
            hi -= 1
    return None

# Multi-key sort: sort by the least significant key first (stable)
rows = [('b', 2), ('a', 1), ('a', 2)]
rows.sort(key=lambda r: r[1])
rows.sort(key=lambda r: r[0])
```

- Two pointers after sorting: O(n log n) total, O(1) extra.

- Stable sorts compose: later sorts preserve earlier key order on ties.

- key= functions beat cmp= for clarity and speed.


## Common mistakes

- Reimplementing quicksort 'for performance' in Python.
  Fix: Timsort in C beats pure-Python quicksort by orders of magnitude.

- Sorting with a cmp function or by repeated single-key sorts unstably.
  Fix: Use key= tuples: sort(key=lambda r: (r[0], r[1])) - one pass, correct.


## Quick checks

Q: Which sort should I actually use?
A: Your language's built-in. Python's timsort is stable, adaptive, and faster than anything you will write in an afternoon. Custom sorts are for learning, exotic constraints, or measured hotspots.


Q: Why does stability matter?
A: Sorting by key B then key A (stable) yields A-major, B-minor order. Unstable sorts scramble the B order within equal A groups - wrong results for multi-key ranking.


## Mental model

Quicksort is organizing a closet by grabbing a random shirt as the divider (pivot) and piling smaller/larger around it, recursively. Mergesort is sorting two halves of a deck separately then riffling them together in order. Timsort notices the deck is already half-sorted and barely shuffles.
