---
skill_id: sys_python_threading
name: Python Threading
description: Threads, the GIL, and writing correct concurrent code.
risk: info
permissions: []
requires_confirmation: false
tags: [python, concurrency]
version: 1.0.0
---
# Python Threading

## Purpose

Threads, the GIL, and writing correct concurrent code.

## Overview

Threads let one process do several things concurrently. In CPython, the GIL (global interpreter lock) allows only one thread to execute Python bytecode at a time - so threads do NOT speed up CPU-bound work. They shine for I/O-bound work: while one thread waits on a socket or disk, the GIL is released and others run. threading.Thread runs a target function; .start() launches, .join() waits. Shared mutable state needs synchronization: Lock for mutual exclusion (use with lock), Queue for thread-safe handoff (it handles locking internally), Event for signaling. Prefer Queue-based designs over shared structures plus manual locking - fewer races, clearer ownership. Daemon threads die with the program; non-daemon threads keep it alive until joined - join your threads or the process hangs at exit. concurrent.futures.ThreadPoolExecutor manages a pool with submit/map and Future results, the modern high-level API. Race conditions are timing-dependent and may never reproduce in testing: keep critical sections small, avoid calling unknown code while holding a lock (deadlock risk), and never assume two threads interleave 'safely' without synchronization. For CPU-bound parallelism, use multiprocessing instead.

## Quick reference

- GIL: one thread runs Python bytecode at a time; threads help I/O, not CPU.

- Thread(target=...): .start() launches, .join() waits.

- Lock (with lock:) for mutual exclusion; Queue for thread-safe handoff.

- Prefer Queue-based designs over shared state + manual locks.

- Join non-daemon threads or the process hangs at exit.

- ThreadPoolExecutor: the modern pool API with Futures.


## Worked example

ThreadPoolExecutor for I/O-bound fan-out:

```
from concurrent.futures import ThreadPoolExecutor
import urllib.request

URLS = ['https://example.com', 'https://example.org']

def fetch_size(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return url, len(r.read())

with ThreadPoolExecutor(max_workers=4) as pool:
    for url, size in pool.map(fetch_size, URLS):
        print(url, size)
```

- Threads wait on network I/O concurrently; the GIL is released during waits.

- The with block shuts the pool down cleanly, joining workers.

- pool.map preserves input order in results.


## Common mistakes

- Sharing a list/dict between threads with no synchronization.
  Fix: Use Queue for handoff or protect access with a Lock.

- Forgetting join(): main exits or hangs with workers still running.
  Fix: Join threads, or use Executor's context manager which joins for you.


## Quick checks

Q: Why didn't threads speed up my computation?
A: The GIL: CPU-bound Python bytecode runs on one thread at a time, so N threads do not parallelize number crunching. Threads help when the bottleneck is waiting (I/O). For CPU work use multiprocessing.


Q: How do I avoid race conditions in practice?
A: Minimize shared mutable state; hand data between threads with Queue; guard the rest with Lock in tiny critical sections; never hold a lock while calling unknown code.


## Mental model

Threads are cooks sharing one stove (the GIL): only one cooks at a time, but while one's pot boils (I/O wait) another chops vegetables. Ten cooks do not boil water faster - they just keep the kitchen busy during the waiting. For real parallel cooking you need more stoves (multiprocessing).
