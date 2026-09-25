---
skill_id: sys_python_context_managers
name: Python Context Managers
description: The with statement: guaranteed setup and teardown for files, locks, and connections.
risk: info
permissions: []
requires_confirmation: false
tags: [python, idiom]
version: 1.0.0
---
# Python Context Managers

## Purpose

The with statement: guaranteed setup and teardown for files, locks, and connections.

## Overview

The with statement guarantees cleanup: the context manager's __enter__ runs on entry, its __exit__ runs on exit - including when exceptions fire or the block returns early. Files are the canonical example: with open(path) closes the file no matter what happens inside. Writing your own is easy two ways: a class implementing __enter__/__exit__, or a generator function decorated with @contextlib.contextmanager where code before yield is setup, yield hands over the resource, and code after yield (usually in try/finally) is teardown. __exit__ receives exception details and can suppress the exception by returning True - powerful, use sparingly. Multiple managers compose in one with statement, and contextlib.ExitStack handles a dynamic number of them. Everyday uses beyond files: locks (threading.Lock), database transactions, temporary directory changes, redirecting stdout in tests, timing blocks. The rule: any resource with acquire/release semantics deserves a context manager, because 'remember to close it' is a bug waiting for a bad day. Never rely on __del__ for cleanup - its timing is not guaranteed.

## Quick reference

- with EXPR as x: __enter__ runs first, __exit__ always runs last.

- __exit__ runs on exceptions and early returns too - cleanup is guaranteed.

- @contextlib.contextmanager: generator-based managers; yield separates setup/teardown.

- Returning True from __exit__ suppresses the exception (use sparingly).

- contextlib.ExitStack: manage a dynamic number of context managers.

- Never rely on __del__ for resource cleanup; use with instead.


## Worked example

A context manager for timing and one for temp state:

```
from contextlib import contextmanager
import time

@contextmanager
def timer(label):
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f'{label}: {time.perf_counter() - start:.3f}s')

with timer('work'):
    total = sum(range(10**6))
```

- Code before yield is setup; after yield (in finally) is teardown.

- Exceptions inside the block propagate through the yield point.

- finally guarantees the timing prints even if the block raises.


## Common mistakes

- Opening files without with and leaking descriptors on exceptions.
  Fix: Always use with open(...); it closes on every exit path.

- Forgetting try/finally around yield in a @contextmanager.
  Fix: Without it, teardown is skipped when the block raises.


## Quick checks

Q: Class-based or @contextmanager - which should I write?
A: contextmanager for the common case: less boilerplate, teardown reads linearly. A class when you need reusable state, methods on the manager, or fine control over __exit__'s exception handling.


Q: Can __exit__ really swallow exceptions? Should it?
A: Yes - return True and the exception is suppressed. Reserve it for managers whose contract includes suppression (like contextlib.suppress); otherwise let errors propagate.


## Mental model

A context manager is a hotel checkout guarantee: you get the room key (__enter__), and no matter how your stay ends - normal checkout, fire alarm, sneaking out early - the front desk settles the bill (__exit__). You never have to remember to return the key yourself.
