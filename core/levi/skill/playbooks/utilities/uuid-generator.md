---
skill_id: utility.uuid_generator
name: UUID Generator
description: Generate random (v4) or namespaced (v5) UUIDs and display them.
risk: info
permissions: []
requires_confirmation: false
tags: [uuid, identifier, generate]
version: 1.0.0
---

# UUID Generator

UUID Generator produces UUIDs on demand: random v4 for fresh identifiers, or deterministic v5 from a namespace and name when you need the same ID every time. Display only.

## When to use

- Minting unique IDs for records or files.
- Generating request IDs for tracing.
- Creating deterministic IDs from stable names.

## Steps

1. For a fresh random ID: uuid.uuid4().
2. For a repeatable ID: uuid.uuid5 with NAMESPACE_URL or NAMESPACE_DNS and your name string.
3. Display the UUID in standard hyphenated form.
4. Generate in bulk when asked, one per line.

## Honest limits

- Standard library only (uuid).
- uuid4 is random, not secret-grade - do not use it as a password or token.
- v5 is deterministic: same namespace plus same name always yields the same UUID, by design.

Original work authored for LEVI - utilities pack.
