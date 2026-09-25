---
skill_id: sys_python_typing
name: Python Type Hints
description: Gradual typing: annotations, generics, and how to get value without fighting the checker.
risk: info
permissions: []
requires_confirmation: false
tags: [python, tooling]
version: 1.0.0
---
# Python Type Hints

## Purpose

Gradual typing: annotations, generics, and how to get value without fighting the checker.

## Overview

Type hints annotate what a value should be - def f(x: int) -> int - without changing runtime behavior; Python ignores them, and checkers like mypy or pyright verify them statically. The win is earlier bug detection and self-documenting signatures: the reader sees the contract without reading the body. Start at boundaries (public functions, data models) where hints pay most, and let inference cover locals. The typing module supplies generics: list[int], dict[str, float], tuple[int, ...], Optional[int] (int | None in 3.10+), Union for either-or. Protocols (structural typing) describe 'has these methods' without inheritance - duck typing made checkable. TypeVar enables generic functions that preserve the input type in the output. Literal, TypedDict, and dataclasses model fixed-shape data precisely. Practical rules: annotate public APIs fully; use the narrowest type that works; prefer int | None over Optional in new code; never lie - a wrong hint is worse than none because checkers trust it. from __future__ import annotations defers evaluation so 3.10+ syntax works on older runtimes. Run the checker in CI; hints nobody verifies rot into misleading comments.

## Quick reference

- Hints are static only; Python ignores them at runtime.

- Annotate public APIs first; inference covers locals.

- list[int], dict[str, int], int | None (3.10+), tuple[int, ...].

- Protocol: structural typing - 'has these methods', no inheritance needed.

- TypeVar: generic functions preserving input->output type relationships.

- TypedDict / dataclasses: precise fixed-shape data.

- Run mypy/pyright in CI; unverified hints rot into lies.


## Worked example

Hints on a small API with a Protocol:

```
from typing import Protocol, TypeVar

class Storable(Protocol):
    def save(self, path: str) -> None: ...

T = TypeVar('T')

def first(items: list[T]) -> T | None:
    return items[0] if items else None

def store_all(objs: list[Storable], path: str) -> None:
    for obj in objs:
        obj.save(path)
```

- Protocol checks structure: any object with save(path) qualifies.

- TypeVar T links the list element type to the return type.

- T | None is the 3.10+ spelling of Optional[T].


## Common mistakes

- Lying hints: annotating -> int while sometimes returning None.
  Fix: The checker trusts you; callers will crash. Annotate the truth.

- Using typing.List/dict legacy generics in new code unnecessarily.
  Fix: Builtin generics (list[int]) work since 3.9; prefer them.


## Quick checks

Q: Do type hints slow down my program?
A: No. They are erased at runtime - plain annotations on functions and variables cost nothing unless some library introspects them. The cost is only the checker's time during development/CI.


Q: Should I annotate everything?
A: Diminishing returns. Annotate public functions, data models, and tricky internals; let inference handle obvious locals. A wrong or stale hint is worse than none - keep them honest.


## Mental model

Type hints are the labels on moving boxes: 'kitchen - fragile'. The movers (the checker) can spot the heavy box labeled fragile before it breaks. The labels do not change what is inside (runtime ignores them), but wrong labels are worse than none - someone will stack accordingly.
