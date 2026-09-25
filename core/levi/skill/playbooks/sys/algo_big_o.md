---
skill_id: sys_algo_big_o
name: Algorithm Big-O Analysis
description: How to reason about growth rates and read complexity like a native.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, cs]
version: 1.0.0
---
# Algorithm Big-O Analysis

## Purpose

How to reason about growth rates and read complexity like a native.

## Overview

Big-O describes how runtime or memory grows as input grows, ignoring constants: O(1) constant, O(log n) halving, O(n) linear scan, O(n log n) efficient sorts, O(n^2) nested loops over the same data, O(2^n) exponential - dead past tiny inputs. Analysis counts the dominant term: drop constants and lower-order terms. Best/average/worst cases differ - quicksort is O(n log n) average but O(n^2) worst; state which you mean. Amortized analysis spreads occasional expensive steps over many cheap ones (list append is O(1) amortized). Space matters too: an O(n) auxiliary structure can be the real constraint. Common traps: hidden loops (in, slicing, and concatenation inside loops), assuming sorted input stays sorted, and confusing n (count the right thing - nodes? edges? digits?). Complexity guides choice but does not decide alone: constants, cache behavior, and n's actual size matter - O(n^2) with tiny n beats O(n log n) with huge constants in practice. Measure after reasoning: profile, do not guess. The skill is quick estimation: spot the loops, find the dominant one, name the growth.

## Quick reference

- O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n): the ladder.

- Drop constants and lower-order terms; name the dominant growth.

- State best/average/worst: quicksort is n log n average, n^2 worst.

- Amortized: list append is O(1) amortized despite occasional resize.

- Watch hidden loops: in, slicing, concat inside loops.

- Complexity guides; measurement decides. Profile, don't guess.


## Worked example

Spotting the dominant term:

```
def pair_sums(nums):
    out = []
    for i in range(len(nums)):       # n
        for j in range(i + 1, len(nums)):  # n/2 avg
            out.append(nums[i] + nums[j])
    return out                        # O(n^2) time, O(n^2) space

def has_dup(nums):
    seen = set()
    for x in nums:                    # n, O(1) avg per op
        if x in seen:
            return True
        seen.add(x)
    return False                      # O(n) time, O(n) space
```

- Nested loops over the same n: the classic O(n^2) signature.

- The set trades O(n) space for O(n) time: the standard time-space trade.

- Comments naming complexity make the reasoning checkable.


## Common mistakes

- Nested loop over the same collection without noticing: accidental O(n^2).
  Fix: Ask 'is there a hash map / sort / two-pointer alternative?'

- Optimizing before profiling: speeding up code that is not the bottleneck.
  Fix: Measure first; complexity analysis points at suspects, profiles convict.


## Quick checks

Q: Is O(n^2) always too slow?
A: Depends on n and constants. n=100: trivial. n=10^6: 10^12 operations - days. Also check constants: an O(n log n) with huge overhead can lose to O(n^2) at small n. Estimate with real numbers, then measure.


Q: What does 'amortized O(1)' mean for list.append?
A: Most appends are O(1); occasionally the list resizes (O(n) copy). Spread over many appends, the average cost per append is constant.


## Mental model

Big-O is rating recipes by how the cooking time grows with guests: O(1) is microwaving one plate no matter the party size; O(n) is plating each guest; O(n^2) is every guest shaking every other guest's hand; O(2^n) is seating arrangements tried exhaustively - fine for 6 guests, heat death for 60.
