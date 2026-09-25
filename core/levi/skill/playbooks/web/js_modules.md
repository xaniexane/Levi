---
skill_id: web_js_modules
name: JavaScript Modules
description: ES modules: import/export, default vs named exports, and how bundlers turn modules into shippable files.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend]
version: 1.0.0
---
# JavaScript Modules
## Purpose
Organize code into modules with explicit dependencies instead of a global soup of scripts.
## Key ideas
- Each module has its own scope; nothing is global unless explicitly attached to window.
- Named exports (export function) allow many per module; default export (export default) allows one.
- Imports are static and hoisted, which lets bundlers tree-shake unused exports.
- Circular imports resolve but leave one side partially initialized; restructure to avoid them.
- Dynamic import() loads modules lazily at runtime, the basis of route-based code splitting.

## In practice
Prefer named exports for utilities and components so imports stay greppable and renames stay safe; reserve default exports for the single main thing a module exists to provide. Keep modules small and single-purpose, importing only what they use, because every import is a dependency edge your bundler and your brain must follow. Break circular imports by extracting the shared piece into a third module rather than tolerating the initialization order puzzle. Split heavy routes with dynamic import() so the initial bundle stays lean; the network cost of one more chunk beats the cost of shipping everything upfront.

```javascript
// math.js
export function add(a, b) { return a + b; }
export const PI = 3.14159;

// app.js
import { add, PI } from "./math.js";
const area = (r) => PI * r * r;

// lazy route loading
async function openReports() {
  const { renderReports } = await import("./reports.js");
  renderReports();
}
```

## Common mistakes
- Mixing default and named exports inconsistently, confusing every importer.
- Creating circular imports that work by accident until an initialization order changes.
- Shipping one giant bundle instead of splitting routes with dynamic import.

## Checklist
- Are exports named by default, with default used only for a module's main thing?
- Is the module graph free of cycles?
- Are heavy routes loaded lazily with dynamic import?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
