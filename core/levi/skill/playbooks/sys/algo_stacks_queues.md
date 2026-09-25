---
skill_id: sys_algo_stacks_queues
name: Algorithm Stacks and Queues
description: LIFO and FIFO: the two orderings that run half of all algorithms.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, data-structures]
version: 1.0.0
---
# Algorithm Stacks and Queues

## Purpose

LIFO and FIFO: the two orderings that run half of all algorithms.

## Overview

A stack is LIFO (last in, first out): push and pop from one end. It models nesting and backtracking - function calls, undo history, depth-first search, bracket matching, expression evaluation. Python lists serve as stacks (append/pop from the end, both O(1) amortized); never pop(0) on a list - that is O(n). A queue is FIFO (first in, first out): enqueue at the back, dequeue from the front - it models waiting lines and breadth-first search. Use collections.deque for queues (popleft is O(1)); queue.Queue adds thread safety. A deque with maxlen is a bounded buffer. Priority queues order by key, not arrival: heapq gives a min-heap (heappush/heappop O(log n)) for schedulers, Dijkstra, and top-k problems. Double-ended queues allow both ends. Choosing: need 'most recent first' (backtrack, undo, DFS)? Stack. Need 'oldest first' (fairness, BFS levels)? Queue. Need 'most important first'? Heap. Monotonic stacks (keeping elements in order while pushing/popping) solve next-greater-element style problems in O(n) - a favorite interview pattern built on this humble structure.

## Quick reference

- Stack = LIFO: push/pop one end. Models nesting, undo, DFS.

- Queue = FIFO: back in, front out. Models lines, BFS. Use deque.

- list as stack: append/pop() O(1). Never pop(0) on a list.

- heapq: min-heap priority queue, O(log n) push/pop.

- deque(maxlen=n): bounded buffer. queue.Queue: thread-safe.

- Monotonic stack: O(n) next-greater-element pattern.


## Worked example

Brackets, BFS levels, and a monotonic stack:

```
from collections import deque

def balanced(s):
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack

def next_greater(nums):
    res, st = [-1] * len(nums), []
    for i, x in enumerate(nums):
        while st and nums[st[-1]] < x:
            res[st.pop()] = x
        st.append(i)
    return res
```

- The stack holds openers; each closer must match the most recent.

- Monotonic stack: each index pushed/popped once - O(n) total.

- deque would serve for queue/BFS; a plain list is ideal for stacks.


## Common mistakes

- pop(0) on a list in a loop: quadratic slowdown.
  Fix: collections.deque for queues; list only as a stack.

- Using a stack where BFS order was needed (or vice versa).
  Fix: DFS/backtracking = stack; level order/fairness = queue.


## Quick checks

Q: Why not just use a list for a queue?
A: list.pop(0) is O(n) - it shifts every element. deque.popleft() is O(1). At thousands of operations the list version visibly drags.


Q: When do I need a priority queue instead of a FIFO?
A: When order should follow importance, not arrival: task schedulers, Dijkstra's cheapest-first expansion, merging k sorted lists, top-k streaming. heapq is the stdlib answer.


## Mental model

A stack is a spring-loaded plate dispenser: you can only take the top plate. A queue is a supermarket line: first arrival checks out first. A priority queue is an ER triage: the most critical patient goes next regardless of arrival time.
