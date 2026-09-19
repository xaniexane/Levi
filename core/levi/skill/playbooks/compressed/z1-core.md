---
skill_id: compressed.z1-core
name: Z-1 Core Engine (advisory)
description: The top compressed layer: primary processing and command logic — how a directive becomes an ordered intent before anything else runs.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, compressed, z1, command, intent]
version: 1.0.0
---
# Z-1 Core Engine (advisory)

## Purpose

Z-1 is the top compression layer of the recovered engine canon (Map A,
Volume 2 "Engine Architecture"): the **Core Engine** holds primary
processing and command logic. Everything else in the canon is a
decompression of this row — zoom in and you get the eight Z-2 groups,
zoom out and you are back here.

## The LEVI-native reading

LEVI's Core reading is: *a directive is not an action; it is a sentence
that must be parsed into an intent before anything runs.* Core never
touches the world. It takes a free-text directive and returns the
structured intent — the verb, the target, the constraints — that the
Workflow layer will later sequence.

## Protocol

1. Read the directive whole; do not act on any word yet.
2. Extract the verb (what is wanted), the target (what it applies to),
   and the constraints (budget, risk ceiling, time, forbidden surfaces).
3. If any of the three is missing, the Core verdict is "under-specified"
   and the directive goes back for clarification — never forward a
   half-parsed intent.
4. Emit the intent as data for the Workflow engine.

Advisory only: this skill advises the pattern; it does not execute, send,
or spend. Execution lives under operator policy and the HITL rail.
