---
skill_id: web_js_variables_scope
name: JavaScript Variables and Scope
description: let, const, and var: block scope, hoisting, and the habits that prevent scope bugs.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend]
version: 1.0.0
---
# JavaScript Variables and Scope
## Purpose
Declare variables with intention so scope behaves the way the code reads.
## Key ideas
- const is the default: it binds the name, though the object it points to can still change.
- let allows reassignment and is block-scoped to the nearest { } pair.
- var is function-scoped and hoisted, which produces surprising reads-before-writes; avoid it in new code.
- Block scope means a variable declared in an if or for block does not leak outside it.
- Temporal dead zone: let and const cannot be read before their declaration line runs.

## In practice
Default to const everywhere and switch to let only when reassignment is genuinely needed; this one habit removes a class of accidental-mutation bugs. Declare variables as close as possible to their first use, inside the smallest block that needs them. When a loop needs the index after it ends, that is a sign to restructure, not to hoist the declaration. If legacy code uses var, convert it during touch-ups: most conversions are mechanical, and each one removes a hoisting trap for the next reader.

```javascript
const TAX_RATE = 0.07;          // never reassigned
let total = 0;                // reassigned in the loop

for (let i = 0; i < items.length; i++) {
  const item = items[i];      // fresh binding each iteration
  total += item.price;
}
// console.log(i); // ReferenceError: i is block-scoped to the loop
```

## Common mistakes
- Using var in new code and tripping over hoisting and function-scope leaks.
- Declaring everything with let out of habit, hiding which values are meant to be stable.
- Reading a let/const before its declaration and meeting the temporal dead zone.

## Checklist
- Is const the default, with let only where reassignment happens?
- Is var absent from new code?
- Are declarations inside the smallest block that needs them?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
