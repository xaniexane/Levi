---
skill_id: sys_python_dataclasses
name: Python Dataclasses
description: Boilerplate-free data holders: fields, defaults, and frozen variants.
risk: info
permissions: []
requires_confirmation: false
tags: [python, idiom]
version: 1.0.0
---
# Python Dataclasses

## Purpose

Boilerplate-free data holders: fields, defaults, and frozen variants.

## Overview

Dataclasses generate the repetitive methods data-holding classes need: @dataclass on a class with annotated fields produces __init__, __repr__, and __eq__ automatically. Fields with defaults must come after fields without; mutable defaults use field(default_factory=list) because a plain [] would be shared across instances - the same trap as mutable default arguments. frozen=True makes instances immutable (hashable too, with eq=True), good for value objects and dict keys. order=True adds comparison methods for sortable records. __post_init__ runs after the generated __init__ for validation or derived fields. Slots (slots=True, 3.10+) cut memory overhead for many small instances. Compared to namedtuple: dataclasses are mutable by default, support defaults and inheritance more naturally, and are clearer for anything beyond a tiny record. Compared to plain dicts: attribute access, type hints, and IDE support make dataclasses the better structured-data choice. Use them for configs, parsed rows, API payloads, and internal messages - anywhere you would otherwise write a five-line __init__ by hand.

## Quick reference

- @dataclass generates __init__, __repr__, __eq__ from annotated fields.

- Mutable defaults need field(default_factory=list), never a bare [].

- frozen=True: immutable, hashable value objects.

- order=True: sortable records. __post_init__: validation after init.

- slots=True (3.10+): lower memory for many instances.

- Prefer dataclasses over dicts for structured data: attributes + hints + IDE help.


## Worked example

A validated, frozen config record:

```
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int = 8080
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError(f'bad port: {self.port}')

cfg = ServerConfig(host='example.com')
print(cfg)
```

- frozen=True blocks attribute reassignment after construction.

- tuple default is safe (immutable); a list default would need default_factory.

- __post_init__ validates while the generated __init__ still does the wiring.


## Common mistakes

- Using a bare [] or {} as a dataclass field default.
  Fix: Use field(default_factory=list/dict).

- Forgetting frozen instances are hashable only if all fields are too.
  Fix: A frozen dataclass holding a list still cannot be hashed.


## Quick checks

Q: dataclass vs namedtuple vs dict - how do I choose?
A: namedtuple for tiny immutable records. dataclass for anything needing defaults, validation, or methods. dict when the shape is dynamic or the data crosses a serialization boundary without a schema.


Q: Why does a list default raise an error in a dataclass?
A: Because it would be shared across all instances - the mutable-default trap. field(default_factory=list) builds a fresh list per instance.


## Mental model

A dataclass is a pre-printed form: the fields are the blanks, the generated __init__ is the clerk who fills them in, and __repr__ is the neat summary stapled on top. You describe the form once instead of hand-writing the clerk's procedure for every new document type.
