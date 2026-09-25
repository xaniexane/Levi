---
skill_id: sys_python_inheritance_dunders
name: Python Inheritance and Dunder Methods
description: Subclassing done right, MRO, and the special methods that make objects Pythonic.
risk: info
permissions: []
requires_confirmation: false
tags: [python, oop]
version: 1.0.0
---
# Python Inheritance and Dunder Methods

## Purpose

Subclassing done right, MRO, and the special methods that make objects Pythonic.

## Overview

Inheritance lets a subclass reuse and specialize a parent class: the child inherits methods and can override them, calling super() to extend rather than replace parent behavior. Python uses the C3 linearization for the method resolution order (MRO) - the deterministic order in which base classes are searched, visible via ClassName.__mro__. Multiple inheritance works but demands discipline: mixins (small classes adding one capability) compose better than deep diamond hierarchies, and every class in the chain should call super().__init__() cooperatively. Abstract base classes (abc.ABC with @abstractmethod) declare interfaces the subclass must implement, failing fast at instantiation instead of at first use. Dunder (double-underscore) methods are the hooks into Python's syntax: __str__ for readable display, __repr__ for unambiguous debugging output, __eq__/__hash__ for value semantics, __len__ and __getitem__ to make an object behave like a sequence, __enter__/__exit__ for context managers, __iter__ for iteration. Implement __repr__ on every class you write - it is what you see in tracebacks and logs. If you define __eq__ without __hash__, Python sets __hash__ to None and your objects become unhashable: decide whether instances are values (hashable) or identities. Operator overloading (__add__ etc.) is for types where the operator has an obvious meaning - vectors, money, dates - not for cleverness.

## Quick reference

- class Child(Parent): inherits; super() calls the parent implementation.

- MRO: C3 linearization order; inspect with ClassName.__mro__.

- Mixins: small single-capability bases; keep hierarchies shallow.

- abc.ABC + @abstractmethod: enforce interface implementation at instantiation.

- __str__ readable, __repr__ unambiguous - always implement __repr__.

- Defining __eq__ clears __hash__; restore it if instances should be hashable.

- __len__/__getitem__/__iter__: sequence protocol. __enter__/__exit__: context managers.


## Worked example

A small value type with dunders and an ABC:

```
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        ...

class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):
        return f'Point({self.x}, {self.y})'

    def __eq__(self, other):
        return (isinstance(other, Point)
                and (self.x, self.y) == (other.x, other.y))

    def __hash__(self):
        return hash((self.x, self.y))

print(Point(1, 2) == Point(1, 2))
```

- ABC with abstractmethod blocks instantiation until area is implemented.

- __repr__ gives the unambiguous developer view used in logs and tracebacks.

- __eq__ plus __hash__ keeps Point usable as a dict key or in a set.


## Common mistakes

- Deep inheritance trees where behavior hides three levels up.
  Fix: Prefer composition and small mixins; two levels is usually enough.

- Forgetting super().__init__() in a subclass, leaving parent state unset.
  Fix: Call it first in the child's __init__ unless you have a reason not to.


## Quick checks

Q: super() vs calling Parent.method(self) directly - does it matter?
A: Yes with multiple inheritance: super() follows the MRO so every class in a cooperative chain runs exactly once. Direct calls hard-code one parent and break the chain for mixins.


Q: Why did defining __eq__ break my dict keys?
A: Python sets __hash__ to None when you define __eq__ without it, making instances unhashable. Add a __hash__ consistent with __eq__, or set __hash__ = None deliberately for mutable value types.


## Mental model

Dunders are the electrical outlets of the object: Python's syntax plugs into them. Define __len__ and len(obj) just works; define __add__ and obj + other works. Inheritance is a family recipe box - the child gets all the cards and may rewrite a few, with super() letting the original card still run.
