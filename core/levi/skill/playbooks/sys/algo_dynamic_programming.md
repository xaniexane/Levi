---
skill_id: sys_algo_dynamic_programming
name: Algorithm Dynamic Programming
description: Solving by remembering: overlapping subproblems, memoization, and tabulation.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, cs]
version: 1.0.0
---
# Algorithm Dynamic Programming

## Purpose

Solving by remembering: overlapping subproblems, memoization, and tabulation.

## Overview

Dynamic programming solves problems with two properties: optimal substructure (the answer builds from optimal answers to subproblems) and overlapping subproblems (the same subproblems recur). The trick is solving each distinct subproblem once and reusing the result. Top-down (memoization): write the natural recursion, cache results (lru_cache) - clearest, pays recursion overhead. Bottom-up (tabulation): fill a table iteratively from base cases - no recursion limit, often optimizable to O(1) space by keeping only needed rows. Recognize DP by the question 'min/max/count ways to ...' with choices at each step and repeated substates. Classic patterns: 0/1 knapsack (take or skip), longest common subsequence (2D table on two strings), coin change (min coins for amount), edit distance. Define the state precisely (dp[i] = best answer for prefix i), write the recurrence, set base cases, choose iteration order so dependencies are ready. Space optimization: if dp[i] only needs dp[i-1], keep two rows. Debugging DP: print the table for a tiny input - wrong recurrences show up immediately as wrong cells.

## Quick reference

- Needs: optimal substructure + overlapping subproblems.

- Top-down: recursion + cache (lru_cache). Bottom-up: iterative table.

- State definition first: dp[i] = exact meaning. Then recurrence, base cases.

- Recognize: min/max/count-ways with stepwise choices and repeated substates.

- Space: keep only needed rows when recurrence is local.

- Debug: print the table on tiny input; wrong cells reveal bad recurrences.


## Worked example

Coin change: top-down and bottom-up:

```
from functools import lru_cache

COINS = (1, 5, 10, 25)

@lru_cache(maxsize=None)
def min_coins_top(amount):
    if amount == 0:
        return 0
    return 1 + min(min_coins_top(amount - c)
                   for c in COINS if c <= amount)

def min_coins_bottom(amount):
    INF = float('inf')
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        dp[a] = 1 + min(dp[a - c] for c in COINS if c <= amount and c <= a)
    return dp[amount]

print(min_coins_top(63), min_coins_bottom(63))
```

- State: min coins for amount; recurrence: 1 + best of (amount - coin).

- Top-down reads like the definition; bottom-up fills dependencies in order.

- lru_cache makes the exponential naive version polynomial.


## Common mistakes

- Vague state definition: dp[i] meaning two things at once.
  Fix: Write the state's exact meaning in a comment before the recurrence.

- Forgetting base cases in tabulation: garbage propagates from row 0.
  Fix: Initialize base cases explicitly and test on the smallest inputs.


## Quick checks

Q: How do I recognize a DP problem?
A: Ask: does the answer build from answers to smaller instances (optimal substructure), and do those instances repeat (overlapping subproblems)? 'Min/max/number of ways' with stepwise choices is the classic smell. Then define the state precisely before writing code.


Q: Top-down or bottom-up?
A: Top-down for clarity and sparse states (only computes needed subproblems). Bottom-up to dodge recursion limits and optimize space. Same complexity class; pick by constraints.


## Mental model

DP is a careful student doing homework: the first time a subproblem appears, solve it and write the answer in the notebook (cache/table). Every later occurrence is just a lookup. Memoization is solving on demand and noting answers; tabulation is filling the whole notebook front to back.
