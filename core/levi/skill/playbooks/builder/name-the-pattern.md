---
skill_id: builder.name_the_pattern
name: Name the Pattern, Not the Textbook
description: Name things after the pattern you actually built, never after a textbook term.
risk: info
permissions: []
requires_confirmation: false
tags: [naming, design, canon]
version: 1.0.0
---

# Name the Pattern, Not the Textbook

When you build something new, its name should describe the pattern in
front of you — not the textbook chapter it resembles. Textbook names
smuggle in expectations your build never agreed to; pattern names keep
the build honest about what it actually does.

## The practice

1. **Describe before you name.** Write one sentence about what the
   thing *does*. The name should fall out of that sentence.
2. **Refuse the borrowed halo.** "Event sourcing", "actor model",
   "CRDT" — if you did not build the textbook thing, do not borrow
   the textbook name to sound like you did.
3. **Let keepers' words stand.** When the keeper names something, that
   name is canon. Do not correct it toward the textbook; translate
   the textbook toward the name if anyone needs translating.
4. **Check for collisions.** A new name must not already mean
   something else in the repo. Two things sharing a name will merge
   in people's heads even if the code keeps them apart.

## The tell

If you need a paragraph to explain why the textbook name does not
quite fit, you do not have a naming problem — you have a different
pattern. Name that one.

## What this is not

This is not an argument against learning the textbooks. Learn them,
absorb them, then let them go. The name serves the build, not the
bibliography.
