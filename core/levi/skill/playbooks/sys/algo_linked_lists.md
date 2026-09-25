---
skill_id: sys_algo_linked_lists
name: Algorithm Linked Lists
description: Node-and-pointer structures: where they win and why arrays usually win.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, data-structures]
version: 1.0.0
---
# Algorithm Linked Lists

## Purpose

Node-and-pointer structures: where they win and why arrays usually win.

## Overview

A linked list chains nodes, each holding a value and a pointer to the next (doubly-linked adds a previous pointer). Insert/delete at a known node is O(1) - just rewiring pointers - and the structure grows without reallocation. The price: no random access (reaching index i is O(i) walking), and each node carries pointer overhead with terrible cache locality - chasing pointers across memory is slow on modern hardware. That is why Python lists (dynamic arrays) beat linked lists for nearly everything: O(1) indexing, cache-friendly, tiny overhead. Linked lists still matter conceptually and in niches: implementing hash-table chains, LRU caches (dict + doubly-linked list), lock-free structures, and wherever O(1) splice at a known position matters. Classic techniques: the fast/slow (tortoise-hare) pointers find cycles and midpoints in one pass; in-place reversal rewires next pointers; dummy head nodes eliminate special-casing empty lists. Interview staple, production rarity - know the pointer manipulations cold, then reach for a list or deque in real code.

## Quick reference

- Node = value + next pointer. O(1) insert/delete at a known node.

- No random access: index i costs O(i). Poor cache locality.

- Python lists (arrays) beat linked lists for almost everything.

- Niches: hash chains, LRU cache, lock-free structures, O(1) splice.

- Fast/slow pointers: cycle detection, midpoint, in one pass.

- Dummy head node removes empty-list special cases.


## Worked example

Fast/slow pointers and in-place reversal:

```
class Node:
    def __init__(self, val, nxt=None):
        self.val, self.next = val, nxt

def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False

def reverse(head):
    prev = None
    while head:
        head.next, prev, head = prev, head, head.next
    return prev
```

- Tortoise-hare: if there's a cycle, fast laps slow; else fast hits None.

- Reversal rewires each next pointer in one pass, O(1) extra space.

- Tuple assignment updates all three links atomically per step.


## Common mistakes

- Losing the rest of the list by overwriting next before saving it.
  Fix: Save nxt = head.next before rewiring, or use tuple assignment.

- Null-dereference in traversal: forgetting the fast/fast.next guards.
  Fix: Check both before advancing two steps.


## Quick checks

Q: Should I ever use a linked list in Python?
A: Almost never directly - list and deque cover the use cases with better constants. Learn the pointer techniques (they appear in interviews and in C-level structures), then use arrays in practice.


Q: Why are linked lists slow despite O(1) insertion?
A: Big-O hides constants: pointer chasing defeats CPU caches, and per-node allocation overhead dwarfs the array's. O(1) with a huge constant loses to O(n) memmove for realistic n.


## Mental model

An array is a street with numbered houses: instant navigation. A linked list is a treasure hunt where each clue gives the next clue's location: inserting a clue mid-hunt is trivial, but reaching clue 50 means visiting 1-49 first.
