---
skill_id: sys_algo_graphs
name: Algorithm Graphs: BFS and DFS
description: Nodes and edges: the two traversals that unlock graphs.
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, data-structures]
version: 1.0.0
---
# Algorithm Graphs: BFS and DFS

## Purpose

Nodes and edges: the two traversals that unlock graphs.

## Overview

A graph is vertices connected by edges (directed or not, weighted or not). Represent sparse graphs with adjacency lists (dict of vertex -> neighbors); dense ones with matrices. DFS (depth-first, stack or recursion) explores as far as possible before backtracking - natural for path-finding, cycle detection, topological sort, and connected components. BFS (breadth-first, queue) expands level by level - and on unweighted graphs, the first time BFS reaches a node is via the shortest path, making it the shortest-path algorithm for that case. Both are O(V + E) with a visited set; forgetting visited on cyclic graphs means infinite loops. Topological sort (Kahn's algorithm or DFS finish order) linearizes DAGs - task scheduling with dependencies. Weighted shortest paths need Dijkstra (non-negative weights, priority queue) or Bellman-Ford (handles negatives, detects negative cycles). Union-find tracks connectivity incrementally (Kruskal's MST). Model first: most graph problems are 'build the graph, then BFS/DFS' - grids are graphs where cells are vertices and moves are edges.

## Quick reference

- Adjacency lists for sparse graphs; matrices for dense.

- DFS (stack): paths, cycles, topo sort, components. BFS (queue): shortest path unweighted.

- Both O(V+E); visited set is mandatory on cyclic graphs.

- Topo sort: linearize DAGs (task scheduling).

- Dijkstra: non-negative weights. Bellman-Ford: negatives + cycle detection.

- Grids are graphs: cells = vertices, moves = edges.


## Worked example

BFS shortest path on a grid:

```
from collections import deque

def shortest_path(grid, start, goal):
    rows, cols = len(grid), len(grid[0])
    q = deque([(start, 0)])
    seen = {start}
    while q:
        (r, c), d = q.popleft()
        if (r, c) == goal:
            return d
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and grid[nr][nc] == 0 and (nr, nc) not in seen):
                seen.add((nr, nc))
                q.append(((nr, nc), d + 1))
    return -1
```

- Queue gives level order; first arrival at goal is the shortest path.

- seen added at enqueue time (not dequeue) prevents duplicate work.

- 0 cells are walkable; bounds checked before access.


## Common mistakes

- No visited set on a cyclic graph: infinite loop.
  Fix: Mark visited at enqueue/push time, always.

- Using DFS for shortest path in unweighted graphs.
  Fix: DFS finds a path, not the shortest. BFS (or Dijkstra if weighted).


## Quick checks

Q: BFS or DFS - how do I decide?
A: Shortest path in unweighted graphs, level-order, or nearest-first: BFS. Path existence, cycle detection, topological order, exploring fully down one branch: DFS. When unsure, BFS's level structure is easier to reason about.


Q: Why does Dijkstra fail with negative weights?
A: Its greedy choice assumes the first-popped node is finalized - a later negative edge could still improve it. Bellman-Ford relaxes repeatedly instead, handling negatives and detecting negative cycles.


## Mental model

DFS is exploring a maze by keeping one hand on the wall and going deep; BFS is a flood filling room by room - the water reaches the exit by the shortest route. Topological sort is writing a recipe's steps in an order where no step comes before its prerequisites.
