---
skill_id: compressed.z1-simulation
name: Z-1 Simulation Engine (advisory)
description: The top compressed layer: modeling of outcomes and scenario planning — rehearsing the future before committing to it.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, compressed, z1, simulation, scenarios]
version: 1.0.0
---
# Z-1 Simulation Engine (advisory)

## Purpose

Z-1 is the top compression layer of the recovered engine canon (Map A,
Volume 2 "Engine Architecture"): the **Simulation Engine** holds modeling
of outcomes and scenario planning. Decisions are cheap to rehearse and
expensive to reverse; this engine runs the rehearsal.

## The LEVI-native reading

LEVI's Simulation reading is: *before committing, walk the plan twice —
once for the expected path, once for the worst plausible path.* Bounded
simulation only: a small set of named scenarios, each with stated
assumptions, each ending in a checkable consequence. Simulation never
claims to predict; it prices the risk so the decider knows what each
choice costs if the assumption breaks.

## Protocol

1. Take the Workflow sequence; name the 2–4 scenarios worth rehearsing
   (expected, worst-plausible, and any load-bearing assumption failing).
2. For each: state the assumption, the consequence, and the earliest
   signal that would show the scenario is the one we're in.
3. Report the scenario set with the verdict — the decision and its
   rehearsal travel together, so a future failure can be composted with
   its assumptions intact.
4. If a scenario's consequence exceeds the risk ceiling, the plan goes
   back — simulation feeds governance, not optimism.

Advisory only: this skill advises the pattern; it does not execute, send,
or spend.
