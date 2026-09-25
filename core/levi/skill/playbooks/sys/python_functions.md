---
skill_id: sys_python_functions
name: Python Functions
description: Defining functions, arguments, scope, and the calling conventions that make code reusable.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Functions

## Purpose

Defining functions, arguments, scope, and the calling conventions that make code reusable.

## Overview

A function packages a computation behind a name: def introduces it, the parameter list declares its inputs, and return hands a result back. Parameters can be positional, keyword, have defaults, or slurp extras with *args and **kwargs. Argument passing in Python is call-by-object-reference: the function receives a reference to the same object, so mutating a passed-in list is visible to the caller while rebinding the parameter name is not. Scope follows the LEGB rule - local, enclosing, global, builtin - and a name assigned inside a function is local unless declared global or nonlocal. Prefer returning values over mutating globals; pure functions (same inputs, same outputs, no side effects) are the easiest to test and reason about. Keyword arguments at call sites act as documentation: connect(timeout=30) reads better than connect(30). Type hints (`def f(x: int) -> int:`) do not change runtime behavior but let linters and readers check intent. Keep functions small and single-purpose; if you cannot name it precisely, it is probably doing two things. Docstrings (the triple-quoted string right under def) are the conventional place to say what it does, what it takes, and what it returns.

## Quick reference

- def name(params): body. return sends a value back; bare return gives None.

- *args collects extra positionals into a tuple; **kwargs collects extra keywords into a dict.

- Keyword-only args after * in the signature force callers to name them.

- LEGB scope: local, enclosing, global, builtin. Assignment defaults to local.

- global/nonlocal declarations let you rebind outer names; avoid when possible.

- Type hints are documentation + tooling, not runtime checks.

- Docstrings: triple-quoted string as the first statement documents the function.


## Worked example

Arguments, defaults, and *args/**kwargs:

```
def greet(name, greeting='Hello', *, loud=False):
    """Greet someone, optionally loudly."""
    msg = f"{greeting}, {name}"
    return msg.upper() if loud else msg

def summarize(*values, **labels):
    return values, labels

print(greet('Ada'))
print(greet('Ada', loud=True))
print(summarize(1, 2, 3, unit='ms'))
```

- Parameters after bare * are keyword-only: callers must write loud=True.

- f-strings interpolate expressions inside braces at runtime.

- *values becomes a tuple, **labels becomes a dict.


## Common mistakes

- Forgetting return and wondering why the function gives None.
  Fix: Every path that should produce a value needs an explicit return.

- Using a mutable default argument to accumulate state across calls.
  Fix: Default to None and create the container inside the function body.


## Quick checks

Q: Does Python pass by value or by reference?
A: Neither exactly: it passes references to objects by value. The function gets its own copy of the reference, pointing at the same object. Mutating the object through it is visible outside; rebinding the parameter name is not.


Q: Why do linters complain about too many arguments?
A: Long parameter lists usually mean the function does too much or takes a grab-bag of flags. Group related values into a dataclass or split the function; keyword-only args at least make call sites readable.


## Mental model

A function is a recipe card: parameters are the blanks for ingredients, the body is the method, and return is the finished dish handed over the counter. Calling it with different arguments is cooking the same recipe with different ingredients - the card never changes.
