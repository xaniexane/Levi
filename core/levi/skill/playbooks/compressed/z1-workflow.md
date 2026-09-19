---
skill_id: compressed.z1-workflow
name: Z-1 Workflow Engine (advisory)
description: The top compressed layer: execution of tasks and process management — turning a parsed intent into an ordered, checkable sequence.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, compressed, z1, workflow, sequencing]
version: 1.0.0
---
# Z-1 Workflow Engine (advisory)

## Purpose

Z-1 is the top compression layer of the recovered engine canon (Map A,
Volume 2 "Engine Architecture"): the **Workflow Engine** holds execution
of tasks and process management. Core parses the intent; Workflow turns
it into a sequence with a shape that can be checked, interrupted, and
resumed.

## The LEVI-native reading

LEVI's Workflow reading is: *a plan is a list of steps with explicit
preconditions, not a paragraph of ambition.* Each step names what it
needs, what it produces, and what "done" looks like. Steps that touch
the world carry their risk tag up front; INFO steps may proceed, anything
heavier waits at the HITL rail. This is the plan half of
Plan→Preview→Permission→Execute→Verify→Receipt — Workflow never runs the
plan itself.

## Protocol

1. Take the Core intent; list the steps in dependency order.
2. Attach to each step: preconditions, expected output, done-criterion,
   risk tag.
3. Surface the risky steps before the run starts, with permission asked
   per step — no blanket approvals.
4. A step that cannot name its done-criterion is not a step; it goes back
   for decomposition.

Advisory only: this skill advises the pattern; it does not execute, send,
or spend. Execution lives under operator policy and the HITL rail.
