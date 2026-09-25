---
skill_id: builder.ship_small
name: Ship Small
description: Break work into the smallest shippable increment and land it before expanding.
risk: info
permissions: []
requires_confirmation: false
tags: [shipping, scope, increments]
version: 1.0.0
---

# Ship Small

A shippable increment is one you can describe in one sentence, test in
one command, and revert in one commit. If your diff needs a paragraph
of explanation to be safe, it is two diffs pretending to be one.

## The practice

1. **Name the smallest landable unit.** The smallest thing that is
   real — a working module with its own test — not the smallest thing
   that is easy.
2. **Land it before the next one starts.** Unlanded work is a promise
   the repo has to keep for you. Keep few promises.
3. **Expand in waves.** Each wave is a whole, tested increment on top
   of a green tree. A half-built second wave never touches the first
   wave's green.
4. **Queue, don't stretch.** When a build wants to grow beyond its
   increment, write it into the build queue and ship what you have.

## The tell

You are shipping too big when the test command takes longer to read
about than to run, or when reverting would take longer than building
did. Halve the scope and ship again.

## What this is not

Shipping small is not shipping thin. Every increment is complete: the
module, its tests, its wiring, its receipt. Thin is a promise without
the work; small is the work without the ceremony.
