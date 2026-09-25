---
skill_id: sys_algo_recursion
name: Algorithm Recursion
description: Thinking recursively: base cases, trust the call, and taming the stack.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, cs]
version: 1.0.0
---
# Algorithm Recursion

## Purpose

Thinking recursively: base cases, trust the call, and taming the stack.

## Overview

Recursion solves a problem by solving smaller instances of itself. Every recursive function needs a base case (the smallest input, solved directly) and a recursive step that provably shrinks toward it - miss either and you get infinite recursion or a RecursionError. The mental model: trust the recursive call to handle the smaller case correctly, and focus only on combining its result - do not trace the whole tree. Recursion depth is limited (Python default 1000 frames) and each frame costs memory: deep linear recursion (linked-list length) risks the limit, while logarithmic depth (binary search, balanced trees) is safe. Python has no tail-call optimization, so 'clever' tail recursion still consumes stack. When recursion fits: tree/graph traversal, divide and conquer, backtracking, and naturally recursive definitions (factorial, Fibonacci - though naive Fibonacci is O(2^n) without memoization). When it does not: deep linear chains (use a loop), or hot paths where call overhead matters. Memoization (lru_cache) converts exponential naive recursion into polynomial by caching subresults - recursion + memoization is often the clearest dynamic programming.

## Quick reference

- Base case + shrinking step: both mandatory, or infinite recursion.

- Trust the recursive call; combine its result. Don't trace the whole tree.

- Depth limit ~1000 in Python; no tail-call optimization.

- Log-depth recursion is safe; linear-depth over big data is not.

- Natural fits: trees, divide-and-conquer, backtracking.

- lru_cache memoization: exponential naive recursion -> polynomial.


## Worked example

Tree recursion with memoization:

```
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    if n < 2:            # base cases
        return n
    return fib(n - 1) + fib(n - 2)   # smaller instances

def tree_sum(node):
    if node is None:     # base case: empty subtree
        return 0
    return node.val + tree_sum(node.left) + tree_sum(node.right)

print(fib(100))
```

- Base cases stop the recursion; the step shrinks n each call.

- lru_cache turns O(2^n) naive Fibonacci into O(n).

- tree_sum trusts the calls on subtrees and just combines.


## Common mistakes

- No base case, or a step that doesn't shrink: RecursionError.
  Fix: Prove termination: every path reaches a base case with smaller input.

- Naive exponential recursion (Fibonacci) without memoization.
  Fix: Add lru_cache or convert to iterative DP.


## Quick checks

Q: How do I debug infinite recursion?
A: Check the two contracts: does a base case exist for every input, and does each call strictly shrink toward it? Print arguments at entry - you will see the non-shrinking call immediately.


Q: Recursion or loop - how do I choose?
A: Recursion when the problem is self-similar (trees, divide-and-conquer) and depth stays modest. Loops for deep linear iteration and hot paths. When in doubt, recursion for clarity, then convert if profiling complains.


## Mental model

Recursion is Russian nesting dolls with instructions: each doll says 'open the smaller doll, then add my part'. The tiniest doll just holds the answer (base case). A missing tiny doll means opening forever; a thousand dolls means the table (stack) collapses.
