---
skill_id: web_js_functions_closures
name: JavaScript Functions and Closures
description: Function declarations, arrow functions, and closures: how inner functions remember their birthplace.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend]
version: 1.0.0
---
# JavaScript Functions and Closures
## Purpose
Use closures deliberately for private state, callbacks, and factories without leaking memory.
## Key ideas
- A closure is a function bundled with the variables that were in scope when it was created.
- Function declarations are hoisted whole; function expressions and arrows are not.
- Arrow functions inherit this from their surroundings; regular functions get this from how they are called.
- Closures enable private state: an outer function's locals stay alive as long as the inner function does.
- Every closure holds its captured variables in memory, so creating them in hot loops has a cost.

## In practice
Use closures for the patterns they fit: event handlers that need configuration, factory functions that mint specialized functions, and module-style private state. Prefer arrow functions for short callbacks where lexical this is what you want, and named function declarations for top-level behavior that benefits from hoisting and a name in stack traces. When a closure outlives its usefulness (a removed DOM node holding a big captured array), null out the reference or remove the listener; otherwise the memory stays pinned. Read a closure by asking what it captured at creation time, not what those variables hold now.

```javascript
function makeCounter(start = 0) {
  let count = start;              // private: only the closure sees it
  return {
    next() { count += 1; return count; },
    reset() { count = start; }
  };
}
const c = makeCounter(10);
c.next(); // 11
c.next(); // 12 -- count persists between calls
```

## Common mistakes
- Creating closures in tight loops that capture large objects, pinning memory unintentionally.
- Using arrow functions as object methods and losing the dynamic this the method needs.
- Assuming a closure sees the current value of a variable rather than the live binding it captured.

## Checklist
- Can you name what each long-lived closure captures?
- Are arrow functions used for callbacks and declarations for named behavior?
- Are listeners and closures released when their DOM or owner is removed?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
