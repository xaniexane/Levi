---
skill_id: sys_python_classes_objects
name: Python Classes and Objects
description: Defining classes, instance vs class state, and the object model underneath.
risk: info
permissions: []
requires_confirmation: false
tags: [python, oop]
version: 1.0.0
---
# Python Classes and Objects

## Purpose

Defining classes, instance vs class state, and the object model underneath.

## Overview

A class is a blueprint; calling it creates an instance, an object with its own state. __init__ runs at construction and sets up instance attributes via self - assignments to self.x live on the instance, while names assigned in the class body are shared class attributes. Methods are functions defined in the class that take self first; Python passes the instance automatically. The distinction matters: mutable class attributes (a list defined in the class body) are shared across ALL instances, a classic surprise when one instance's append shows up in another's. Properties (@property) expose computed attributes behind attribute syntax, letting you add validation or lazy computation later without changing callers. Class methods (@classmethod, taking cls) construct or configure at the class level - alternate constructors like from_dict are the canonical use. Static methods (@staticmethod) are namespaced helpers with no instance or class access. Python has no true privacy: a single leading underscore is a 'please don't touch' convention, double underscore triggers name mangling to _ClassName__attr to avoid subclass collisions. Dataclasses remove the boilerplate for data-holding classes, generating __init__, __repr__, and __eq__ from field declarations. Design guidance: prefer composition (holding other objects) over deep inheritance trees, and keep classes focused on one responsibility.

## Quick reference

- class C: blueprint. C() constructs; __init__(self, ...) sets instance state.

- self.x: per-instance. Class-body names: shared across instances.

- Methods take self; @classmethod takes cls; @staticmethod takes neither.

- @property: computed attribute with getter/setter syntax.

- _name: private by convention. __name: name-mangled to avoid collisions.

- dataclasses auto-generate __init__/__repr__/__eq__ for data classes.

- Prefer composition over deep inheritance; one responsibility per class.


## Worked example

Instance vs class state, property, alternate constructor:

```
from dataclasses import dataclass

class Account:
    bank = 'First Bank'          # class attribute: shared

    def __init__(self, owner, balance=0):
        self.owner = owner        # instance attributes
        self._balance = balance

    @property
    def balance(self):
        return self._balance

    @classmethod
    def from_pair(cls, pair):
        owner, balance = pair
        return cls(owner, balance)

a = Account.from_pair(('Ada', 100))
print(a.owner, a.balance, a.bank)
```

- bank lives on the class: every account sees it until shadowed.

- @property lets a.balance read like an attribute while running a method.

- from_pair is an alternate constructor - the idiomatic classmethod use.


## Common mistakes

- Forgetting self in a method signature: confusing TypeErrors at call time.
  Fix: Instance methods always take self first; Python fills it in.

- Mutable class attribute shared across instances.
  Fix: Initialize mutable state in __init__, not in the class body.


## Quick checks

Q: Why did my change to one instance affect all of them?
A: You mutated a class attribute - a mutable object defined in the class body is shared by every instance. Assign per-instance state inside __init__ via self instead.


Q: When is @classmethod the right tool vs @staticmethod?
A: classmethod when the method needs the class itself - alternate constructors that must work for subclasses. staticmethod when it is just a namespaced helper needing neither instance nor class.


## Mental model

A class is an architectural blueprint; instances are the houses built from it. Each house has its own paint color (instance attributes), but they all share the street name on the blueprint (class attributes) - repaint the street sign and every house's address changes.
