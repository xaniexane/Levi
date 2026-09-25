---
skill_id: web_js_dom_basics
name: JavaScript DOM Basics
description: Find, read, and change page content with the DOM: selectors, node updates, and batching changes.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend, dom]
version: 1.0.0
---
# JavaScript DOM Basics
## Purpose
Manipulate the document efficiently and safely, with minimal reflow and no injection holes.
## Key ideas
- querySelector and querySelectorAll find elements with CSS selectors; getElementById is the fastest single lookup.
- textContent sets plain text safely; innerHTML parses HTML and must never receive untrusted strings.
- Changes to the live DOM trigger reflow; batch reads and writes or build offscreen in a fragment.
- createElement plus appendChild builds nodes safely; template literals into innerHTML do not.
- The DOM is a tree: parentNode, children, and closest() navigate it without re-querying the document.

## In practice
Treat innerHTML as a power tool with the guard off: fine for your own static templates, forbidden for anything containing user data, where textContent or createElement are the safe paths. When updating lists, build the new nodes in a DocumentFragment and swap once, instead of appending in a loop and reflowing per item. Cache element references you touch repeatedly rather than re-querying; querySelector on every frame is a performance smell. After dynamic updates, check that focus and ARIA states still make sense; a screen reader user experiences your DOM surgery as the interface itself.

```javascript
const list = document.querySelector("#orders");
const frag = document.createDocumentFragment();

for (const o of orders) {
  const li = document.createElement("li");
  li.textContent = `Order ${o.id}: $${o.total}`; // safe: text, not HTML
  frag.appendChild(li);
}
list.replaceChildren(frag); // one DOM write, one reflow
```

## Common mistakes
- Injecting user data via innerHTML, opening a direct cross-site scripting hole.
- Appending nodes in a loop, paying a reflow per item on large lists.
- Re-querying the same elements repeatedly instead of caching references.

## Checklist
- Is untrusted content set with textContent/createElement, never innerHTML?
- Are bulk DOM updates batched through fragments or single writes?
- Do dynamic updates preserve sensible focus and ARIA state?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
