---
skill_id: sys_os_memory_stack_heap
name: OS Memory: Stack vs Heap
description: Where variables live: automatic storage, dynamic allocation, and lifetimes.
risk: info
permissions: []
requires_confirmation: false
tags: [os, memory]
version: 1.0.0
---
# OS Memory: Stack vs Heap

## Purpose

Where variables live: automatic storage, dynamic allocation, and lifetimes.

## Overview

A process's memory divides into regions: the stack holds function frames (locals, return addresses) growing and shrinking automatically as functions call and return; the heap holds dynamically allocated objects with programmer- (or GC-) managed lifetimes; static/global segments hold fixed data; code lives in the text segment. Stack allocation is a pointer bump - blazing fast - and cleanup is automatic, but frames are small (typical stack limit ~8 MB) and die with the function: returning a pointer to a local is the classic dangling bug in C. Heap allocation (malloc/new) serves arbitrary sizes and lifetimes but costs bookkeeping, fragments over time, and leaks if never freed (in manual languages). Python hides this: names bind to heap objects, reference counting + a cycle collector frees them, and the C stack still bounds recursion depth. Cache locality follows layout: stack and contiguous arrays stream through caches; pointer-chasing across the heap stalls. Practical takeaways: prefer automatic (stack) storage for short-lived data, beware deep recursion (stack overflow), and in Python remember every object is heap-allocated - which is why small ints and strings get cached/interned and why numpy arrays beat Python lists for numerics (contiguous C memory).

## Quick reference

- Stack: function frames, automatic, fast, small, dies with the call.

- Heap: dynamic objects, flexible lifetime, needs management (or GC).

- Returning a stack address (C) = dangling pointer bug.

- Deep recursion risks stack overflow; Python caps at ~1000 frames.

- Contiguous layout (arrays) is cache-friendly; pointer chasing is not.

- Python: all objects on the heap; refcount + cycle collector frees them.


## Worked example

Lifetimes: what survives the return:

```
# C: the classic dangling pointer (do NOT do this)
# int *f(void) { int x = 42; return &x; }  // x dies with the frame

# Python: names bind heap objects; refcount frees them
def make():
    data = [1, 2, 3] * 1000   # heap object
    return data               # reference survives; object lives on

import sys
a = [1, 2, 3]
print(sys.getrefcount(a))     # references keeping it alive
print(sys.getsizeof([1]*100)) # contiguous array of pointers
```

- Python returns the reference: the heap object outlives the frame.

- getrefcount shows live references (note: the call itself adds one).

- In C, returning &x hands out a dead stack address.


## Common mistakes

- Deep recursion on big data in Python: RecursionError.
  Fix: Convert to iteration or raise the limit deliberately (with care).

- In C: returning pointers to locals; in Python: assuming locals are 'free'.
  Fix: Python objects live on the heap - locals just drop references.


## Quick checks

Q: Why is stack allocation faster than heap?
A: It is a pointer bump with no search or bookkeeping, and deallocation is free (the frame pops). Heap allocation searches free lists, may fragment, and needs explicit or GC'd release.


Q: What actually is a stack overflow?
A: Exhausting the stack region: unbounded or very deep recursion, or huge stack buffers (in C). The guard page faults and the process dies - Python raises RecursionError before the C stack is at risk.


## Mental model

The stack is a cafeteria tray dispenser: take a tray (call), pile food (locals), return it when done - spring-loaded and automatic. The heap is renting storage units: any size, keep as long as you pay (manage), lose the key (leak) and you pay forever.
