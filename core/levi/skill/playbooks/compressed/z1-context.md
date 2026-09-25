---
skill_id: compressed.z1-context
name: Z-1 Context Engine (advisory)
description: The top compressed layer: memory, continuity, and situational awareness — what the system knows before it judges.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, compressed, z1, context, memory]
version: 1.0.0
---
# Z-1 Context Engine (advisory)

## Purpose

Z-1 is the top compression layer of the recovered engine canon (Map A,
Volume 2 "Engine Architecture"): the **Context Engine** holds memory,
continuity, and situational awareness. A verdict without context is a
guess wearing a uniform.

## The LEVI-native reading

LEVI's Context reading is: *no engine judges on the input alone.* Before
a verdict, the engine assembles a situational snapshot — who asked, what
has been decided before, what constraints are live, what changed since
last time. Context is read, never invented: if the memory store has no
record, the snapshot says "unknown" rather than confabulating.

## Protocol

1. Gather the live facts: the directive, the requester, the active
   constraints, the recent related decisions.
2. Mark each fact sourced (memory record), fresh (input), or unknown —
   never blur the three.
3. Hand the snapshot to the deciding engine alongside the input; the
   snapshot travels with the verdict's trace so the judgment is auditable.
4. Unknowns widen the trace, never the confidence.

Advisory only: this skill advises the pattern; it does not execute, send,
or spend.
