---
skill_id: sys_python_data_types
name: Python Data Types and Mutability
description: Python's core data types, how mutability works, and why it changes how your code behaves.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Data Types and Mutability

## Purpose

Python's core data types, how mutability works, and why it changes how your code behaves.

## Overview

Python has a small set of built-in types that cover most programs: integers, floats, complex numbers, booleans, strings, bytes, lists, tuples, sets, frozensets, and dictionaries. Every value in Python is an object, and every object has a type, an identity, and a value. The key split is between mutable and immutable types. Immutable types - int, float, str, tuple, frozenset - cannot change in place: an operation that looks like a change actually builds a brand new object. Mutable types - list, dict, set, bytearray - can be changed in place, which means two names pointing at the same object will both see the change. This aliasing is the source of the classic mutable-default-argument bug: a default list in a function signature is created once, shared across calls, and quietly accumulates state. Numbers deserve a note: Python integers have arbitrary precision, so they never overflow the way 32-bit ints do in C, at the cost of speed. Floats are IEEE 754 doubles, so 0.1 + 0.2 is 0.30000000000000004 - a representation artifact, not a bug. Strings are immutable sequences of Unicode characters; bytes are immutable sequences of small ints for raw data. Choose the type that matches the semantics: a tuple for a fixed record, a list for a growing sequence, a set for membership tests, a dict for key lookup. Getting the type right at the start prevents a whole class of later bugs.

## Quick reference

- int/float/complex/bool: numbers. bool is a subclass of int (True == 1).

- str: immutable Unicode text. bytes: immutable raw data. bytearray: mutable raw data.

- list: ordered, mutable. tuple: ordered, immutable - use for fixed records.

- dict: key to value mapping, mutable. set/frozenset: unordered unique items.

- None: the single null value, of type NoneType. Use `is None`, never `== None`.

- Mutability rule: immutable ops return new objects; mutable ops change in place.

- Never use a mutable object as a function default argument; use None and build inside.


## Worked example

Mutability and aliasing in action:

```
a = [1, 2, 3]
b = a            # b is the SAME list, not a copy
b.append(4)
print(a)         # [1, 2, 3, 4] -- a changed too

c = a.copy()     # a real copy
c.append(5)
print(a)         # [1, 2, 3, 4] -- untouched
print(c)         # [1, 2, 3, 4, 5]

def add_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

- b = a binds a second name to the same list object; append mutates it.

- list.copy() makes a shallow copy: enough for flat lists of immutables.

- The bucket=None pattern avoids the shared-mutable-default trap.


## Common mistakes

- Using `==` with None: `if x == None` can misbehave with objects that overload equality; `if x is None` is the correct identity check.
  Fix: Always compare against None with `is` / `is not`.

- Mutating a list while iterating over it, skipping elements.
  Fix: Iterate over a copy (`for x in items[:]`) or build a new list.


## Quick checks

Q: Why is 0.1 + 0.2 not exactly 0.3 in Python?
A: Floats are binary fractions (IEEE 754 doubles). 0.1 has no exact binary representation, so the stored values are the nearest representable numbers and their sum shows the rounding error. For money, use decimal.Decimal or integer cents.


Q: When should I use a tuple instead of a list?
A: When the collection is a fixed-shape record whose length and meaning do not change - coordinates, RGB values, a database row. Immutability makes it hashable so it can be a dict key, and it signals intent to readers.


## Mental model

Think of immutable objects as printed photographs and mutable objects as whiteboards. Handing someone a photograph means they can look but never alter your copy - any edit forces them to print their own. Handing someone a whiteboard marker means every scribble shows up on your board too. Python names are just sticky notes pointing at boards and photographs.
