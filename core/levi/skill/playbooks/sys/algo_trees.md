---
skill_id: sys_algo_trees
name: Algorithm Trees
description: Hierarchies in memory: binary trees, BSTs, traversals, and heaps.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, data-structures]
version: 1.0.0
---
# Algorithm Trees

## Purpose

Hierarchies in memory: binary trees, BSTs, traversals, and heaps.

## Overview

A tree is nodes with parent-child edges and no cycles; a binary tree gives each node up to two children. Depth-first traversals - inorder (left, node, right), preorder (node first), postorder (node last) - visit every node in O(n); inorder on a binary search tree yields sorted order. A BST orders values (left < node < right) giving O(log n) search/insert/delete when balanced, O(n) when degenerate - hence self-balancing variants (AVL, red-black) and why Python's bisect on sorted lists or sortedcontainers often suffices practically. Breadth-first (level order, via queue) visits level by level. A heap is a complete binary tree with the heap property (parent <= children for min-heap): O(log n) push/pop, O(1) peek at the extreme - the engine behind priority queues and top-k. Recursion is the natural traversal language (base case: None), but iterative versions with explicit stacks avoid depth limits on skewed trees. Trie (prefix tree) indexes strings by prefix for autocomplete and spell-check. Segment trees/fenwick answer range queries fast. Rule of thumb: hierarchical data or ordered operations -> think trees; need a dict? Python's dict already is a hash table - trees earn their keep for ordering and ranges.

## Quick reference

- Binary tree: <= 2 children. Traversals: inorder/preorder/postorder, all O(n).

- BST: left < node < right. O(log n) balanced, O(n) degenerate.

- BFS (queue): level order. DFS (stack/recursion): depth first.

- Heap: complete tree + heap property. O(log n) push/pop, O(1) peek.

- Trie: prefix indexing for strings. Segment tree: range queries.

- dict covers unordered; trees earn keep for ordering and ranges.


## Worked example

BST insert/search and heap top-k:

```
import heapq

class BST:
    def __init__(self, val, left=None, right=None):
        self.val, self.left, self.right = val, left, right

def bst_insert(root, val):
    if root is None:
        return BST(val)
    if val < root.val:
        root.left = bst_insert(root.left, val)
    elif val > root.val:
        root.right = bst_insert(root.right, val)
    return root

def top_k(nums, k):
    return heapq.nlargest(k, nums)   # heap-powered, O(n log k)

root = None
for v in [5, 3, 7, 1]:
    root = bst_insert(root, v)
print(top_k([4, 1, 7, 3, 9], 2))
```

- BST insert recurses to a leaf; duplicates ignored here by policy.

- heapq.nlargest keeps a k-sized heap: O(n log k), not full sort.

- Inorder traversal of this BST would print 1 3 5 7.


## Common mistakes

- Assuming BST operations are O(log n) on adversarial input.
  Fix: Sorted input degenerates it; balance or use sortedcontainers/bisect.

- Recursive traversal on a 10^6-deep chain: RecursionError.
  Fix: Use iterative traversal with an explicit stack for deep trees.


## Quick checks

Q: BST vs hash table - when does the tree win?
A: Ordered operations: sorted iteration, range queries, predecessor/successor, nearest key. Hash tables cannot order. If you only need lookup, the hash table's O(1) wins.


Q: Why is a degenerate BST O(n)?
A: Inserting sorted data without balancing builds a chain - each insert walks the full length. Self-balancing trees (or shuffling input) keep the O(log n) guarantee.


## Mental model

A BST is a 'guess the number' game frozen into a structure: each node asks 'higher or lower', halving the search. A heap is a tournament bracket where the champion (min/max) always sits on top and a new challenger climbs in O(log n) matches.
