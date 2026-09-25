---
skill_id: sys_python_decorators
name: Python Decorators
description: Functions that wrap functions: the @ syntax, arguments, and everyday uses.
risk: info
permissions: []
requires_confirmation: false
tags: [python, idiom]
version: 1.0.0
---
# Python Decorators

## Purpose

Functions that wrap functions: the @ syntax, arguments, and everyday uses.

## Overview

A decorator is a callable that takes a function and returns a (usually wrapped) function. The @ syntax is sugar: @dec above def f is exactly f = dec(f). The wrapper typically calls the original, adding behavior before or after - timing, logging, caching, access checks, retry logic. functools.wraps copies the original's name and docstring onto the wrapper; without it, every decorated function reports as 'wrapper' in tracebacks and help(). Decorators with arguments need one more nesting level: an outer factory takes the arguments and returns the actual decorator. Order matters when stacking: @a above @b means a(b(f)) - b applies first, a outermost. Class-based decorators (implementing __call__) hold state across calls, useful for rate limiters or registries. Common stdlib decorators: @lru_cache for memoization, @property/@classmethod/@staticmethod for the object model, @contextmanager for quick context managers. Keep decorators focused on cross-cutting concerns; business logic hidden in decorators surprises readers. And remember decorators run at import/definition time, not at call time - expensive work in the decorator body happens once per definition.

## Quick reference

- @dec is sugar for f = dec(f); decorators run at definition time.

- functools.wraps preserves __name__ and __doc__ on the wrapper.

- Decorator factories: outer(args) returns the decorator for @dec(args).

- Stacking: @a over @b applies b first; a is outermost.

- @lru_cache: memoization. @property/@classmethod: object model hooks.

- Use decorators for cross-cutting concerns (timing, retry, auth), not business logic.


## Worked example

A timing decorator with functools.wraps:

```
import functools, time

def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            dt = time.perf_counter() - start
            print(f'{func.__name__} took {dt:.3f}s')
    return wrapper

@timed
def fetch(n):
    return sum(range(n))
```

- functools.wraps keeps fetch.__name__ == 'fetch' for logs and tracebacks.

- try/finally times the call even when it raises.

- *args/**kwargs make the wrapper transparent to any signature.


## Common mistakes

- Forgetting functools.wraps, breaking introspection and stacked decorators.
  Fix: Always wrap the inner function with functools.wraps.

- Doing expensive work in the decorator body, paying it at import time.
  Fix: Keep the body cheap; do work inside the wrapper at call time.


## Quick checks

Q: Why does my decorated function show the wrong name in tracebacks?
A: The wrapper replaced it without copying metadata. Add @functools.wraps(func) to the wrapper and __name__, __doc__, and __module__ carry over.


Q: When do I need a decorator factory instead of a plain decorator?
A: When the decorator itself takes arguments, like @retry(times=3). The outer function receives the arguments and returns the real decorator.


## Mental model

A decorator is a gift-wrapping station for functions: the gift (original function) goes in unchanged, and comes out in wrapping paper (added behavior) with the same gift tag (name, thanks to functools.wraps). Stacking decorators is wrapping the wrapped box again.
