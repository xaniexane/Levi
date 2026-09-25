---
skill_id: sys_python_multiprocessing
name: Python Multiprocessing
description: True parallelism with processes: when and how to use them.
risk: info
permissions: []
requires_confirmation: false
tags: [python, concurrency]
version: 1.0.0
---
# Python Multiprocessing

## Purpose

True parallelism with processes: when and how to use them.

## Overview

multiprocessing sidesteps the GIL by using separate processes, each with its own interpreter and memory - real parallelism for CPU-bound work, at the cost of heavier startup and no shared memory by default. Data crosses the boundary by pickling through pipes/queues, so arguments and results must be picklable and large transfers get expensive. concurrent.futures.ProcessPoolExecutor is the friendly API: submit/map over a function and an iterable, collect results. The worker function must be importable (top-level, not a lambda or closure) because the child re-imports your module - which is why the if __name__ == '__main__' guard is mandatory on Windows/macOS spawn. Shared state options exist (Value, Array, Manager) but shared-nothing via task queues is simpler and safer. Overhead matters: process startup is milliseconds-to-hundreds-of-ms, so chunk many small items into fewer tasks (chunksize). Rule of thumb: threads for I/O-bound, processes for CPU-bound, asyncio for many lightweight I/O connections in one thread. Profile first - the overhead can exceed the gain on small workloads.

## Quick reference

- Processes bypass the GIL: true parallelism for CPU-bound work.

- No shared memory by default; data crosses via pickling (must be picklable).

- ProcessPoolExecutor: submit/map, the high-level API.

- Workers must be importable top-level functions; guard with __main__.

- Chunk small items (chunksize) to amortize process startup cost.

- Threads = I/O-bound, processes = CPU-bound, asyncio = many light connections.


## Worked example

Process pool for CPU-bound work:

```
from concurrent.futures import ProcessPoolExecutor

def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True

def main():
    nums = range(10**5, 10**5 + 4000)
    with ProcessPoolExecutor() as pool:
        primes = [n for n, p in zip(nums, pool.map(is_prime, nums,
                                                 chunksize=100)) if p]
    print(len(primes), 'primes found')

if __name__ == '__main__':
    main()
```

- is_prime is top-level and picklable: required for worker functions.

- chunksize=100 amortizes per-task overhead across batches.

- The __main__ guard prevents infinite child respawn on spawn platforms.


## Common mistakes

- Missing the __main__ guard: infinite process spawn loop.
  Fix: Always guard pool creation under if __name__ == '__main__'.

- Passing huge objects per task, paying pickle costs repeatedly.
  Fix: Share read-only big data via initializer, or chunk smarter.


## Quick checks

Q: Why must the worker be a top-level function?
A: The child process re-imports your module and looks the function up by name. Lambdas and closures cannot be pickled by reference, so they fail. Top-level def it is.


Q: multiprocessing made it slower - what happened?
A: Overhead dominated: pickling big arguments/results plus process startup cost more than the compute saved. Use bigger chunks, smaller payloads, or confirm the work is actually CPU-bound first.


## Mental model

Processes are separate kitchens in separate buildings: each has its own stove (no GIL contention), but ingredients travel by delivery truck (pickling) - fast for recipe cards (small args), slow for grand pianos (huge objects). Threads shared one kitchen; processes pay delivery fees.
