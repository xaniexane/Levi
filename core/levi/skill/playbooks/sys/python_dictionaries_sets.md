---
skill_id: sys_python_dictionaries_sets
name: Python Dictionaries and Sets
description: Hash-based collections: dicts for lookup, sets for membership, and how hashing drives both.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python Dictionaries and Sets

## Purpose

Hash-based collections: dicts for lookup, sets for membership, and how hashing drives both.

## Overview

Dictionaries map keys to values with average O(1) lookup, insertion, and deletion, powered by a hash table under the hood. Keys must be hashable - immutable types like strings, numbers, and tuples of immutables - because the hash decides the storage slot; mutating a key in place would strand its value. Since Python 3.7, dicts preserve insertion order, so they double as ordered records. The .get() method returns a default instead of raising KeyError, and setdefault() inserts-and-returns in one step; collections.defaultdict goes further by auto-creating missing entries, which cleans up grouping code. Dict merge with | (3.9+) and unpacking with ** make combining mappings declarative. Sets hold unique hashable items and answer membership questions in O(1) - `x in my_set` beats scanning a list the moment the data grows. Set algebra (union |, intersection &, difference -, symmetric difference ^) expresses data-comparison tasks directly: which users are in A but not B is just a - b. Deduplication is set(items) when order does not matter, or dict.fromkeys(items) when it does. Watch the gotchas: iterating a dict yields keys; mutating a dict's size during iteration raises RuntimeError; and two objects that compare equal must hash equal or the table breaks - which is why custom classes used as keys should define both __eq__ and __hash__.

## Quick reference

- dict: key->value, O(1) avg lookup. Keys must be hashable and immutable.

- d.get(k, default), d.setdefault(k, default), defaultdict for grouping.

- Merge: d1 | d2 (3.9+); unpack: {**d1, **d2}.

- set: unique items, O(1) membership. frozenset: immutable, hashable set.

- Set ops: | union, & intersection, - difference, ^ symmetric difference.

- Dedupe keeping order: list(dict.fromkeys(items)).

- Never change a dict's size while iterating it; iterate over list(d) if needed.


## Worked example

Grouping with defaultdict and set algebra:

```
from collections import defaultdict

words = ['apple', 'avocado', 'banana', 'blueberry', 'cherry']
by_letter = defaultdict(list)
for w in words:
    by_letter[w[0]].append(w)
print(dict(by_letter))

team_a = {'ada', 'bo', 'cy'}
team_b = {'bo', 'cy', 'dee'}
print('both:', team_a & team_b)
print('only a:', team_a - team_b)
```

- defaultdict(list) creates an empty list on first access to a new key.

- & is intersection, - is difference; both return new sets.

- Set elements must be hashable: no lists or dicts inside a set.


## Common mistakes

- KeyError from d[k] on a possibly-missing key in a hot path.
  Fix: Use d.get(k) with a default, or check membership first.

- Putting a list inside a set or as a dict key: TypeError: unhashable.
  Fix: Convert to tuple (or frozenset) first.


## Quick checks

Q: Why must dict keys be immutable?
A: The hash of the key picks its storage bucket. If the key mutated after insertion, its hash would change and the entry would be unreachable in its old bucket. Immutability guarantees the hash stays valid for the key's life.


Q: dict vs a list of pairs - when does the dict win?
A: Whenever you look things up by key more than a handful of times. A list scan is O(n) per lookup; a dict is O(1) average. For tiny fixed data a list of pairs is fine, but anything searched repeatedly belongs in a dict.


## Mental model

A dict is a coat-check counter: you hand over your coat (value) and get a numbered ticket (key); retrieval is instant because the ticket maps straight to the hook. A set is the bouncer's guest list: the only question is 'are you on the list', answered with one glance instead of reading every name.
