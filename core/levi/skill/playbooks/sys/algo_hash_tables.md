---
skill_id: sys_algo_hash_tables
name: Algorithm Hash Tables
description: How hash tables work: hashing, collisions, and why dict is O(1).
risk: info
permissions: []
requires_confirmation: false
tags: [algorithms, data-structures]
version: 1.0.0
---
# Algorithm Hash Tables

## Purpose

How hash tables work: hashing, collisions, and why dict is O(1).

## Overview

A hash table maps keys to buckets by hashing the key: index = hash(key) mod capacity, giving average O(1) insert/lookup/delete. Collisions (two keys, one bucket) resolve by chaining (linked lists per bucket) or open addressing (probing for the next free slot - Python dicts use a variant). Good hash functions spread keys uniformly; bad ones cluster and degrade toward O(n). Load factor (entries / capacity) triggers resizing: double the table and rehash everything - an O(n) operation amortized across inserts. The contract that makes it all work: equal objects must hash equal (a == b implies hash(a) == hash(b)), and a key's hash must not change while stored - hence immutability for keys. Python dict/set are hash tables; that is where their O(1) average comes from, and why unhashable types (lists) are rejected. Worst cases are real: hash-flooding attacks feed colliding keys to force O(n^2) behavior - Python randomizes string hashing (PYTHONHASHSEED) as a defense. Use hash tables for lookup, dedup, counting, and memoization; prefer them over sorted structures unless ordering matters.

## Quick reference

- index = hash(key) % capacity: O(1) average via hashing.

- Collisions: chaining (lists per bucket) or open addressing (probing).

- Load factor triggers resize-and-rehash: O(n), amortized across inserts.

- Contract: a == b => hash(a) == hash(b); keys must be immutable.

- Python dict/set are hash tables: O(1) avg, unhashable keys rejected.

- Hash flooding: colliding keys -> O(n^2); Python randomizes string hashes.


## Worked example

A tiny hash table with chaining:

```
class TinyMap:
    def __init__(self, capacity=8):
        self.buckets = [[] for _ in range(capacity)]

    def _idx(self, key):
        return hash(key) % len(self.buckets)

    def put(self, key, value):
        bucket = self.buckets[self._idx(key)]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))

    def get(self, key, default=None):
        for k, v in self.buckets[self._idx(key)]:
            if k == key:
                return v
        return default
```

- Chaining: each bucket holds a list of (key, value) pairs.

- put updates in place on key match, else appends.

- Real tables resize on load factor; this one keeps the mechanics visible.


## Common mistakes

- Mutating an object used as a dict key: entry becomes unreachable.
  Fix: Keys must be immutable for their whole stored lifetime.

- Defining __eq__ without __hash__: instances become unhashable.
  Fix: Provide both, consistently, or accept unhashability.


## Quick checks

Q: Why must equal objects hash equal?
A: Lookup computes the bucket from the hash. If a == b but the hashes differed, the search would look in the wrong bucket and miss the entry - the table's core promise breaks.


Q: When do hash tables degrade to O(n)?
A: Mass collisions (bad hash function or adversarial keys) turn buckets into long chains, and lookups scan them linearly. Plus the rare full rehash. Randomization and good hash functions keep this theoretical.


## Mental model

A hash table is a library that shelves books by a code computed from the title: you compute the code and walk straight to the shelf (O(1)) instead of scanning every spine. Collisions are two books with the same code sharing a shelf slot - you check the few there.
