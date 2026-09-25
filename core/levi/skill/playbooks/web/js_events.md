---
skill_id: web_js_events
name: JavaScript Events
description: The event system: listeners, bubbling, delegation, and preventing default browser behavior.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend, dom]
version: 1.0.0
---
# JavaScript Events
## Purpose
Wire up interaction that stays correct as the DOM changes under it.
## Key ideas
- addEventListener attaches handlers without clobbering others; one element can have many listeners.
- Events bubble from the target up through ancestors; capture phase runs the other way down.
- Event delegation puts one listener on a parent and inspects event.target, covering future children too.
- preventDefault stops the browser's native action (form submit, link navigation); stopPropagation halts bubbling.
- Remove listeners (or use { once: true }) when their element or purpose is gone to avoid leaks.

## In practice
Default to delegation for lists and dynamic content: one listener on the container, a closest() check for the actionable child, and it works for rows added later without re-binding. Call preventDefault only when you truly replace the native behavior, and stopPropagation sparingly; over-stopping breaks other features listening higher up, including analytics and accessibility helpers. Name handler functions instead of inlining anonymous ones so they can be removed and appear in stack traces. For one-shot handlers like onboarding tooltips, the once option removes the listener automatically and documents the intent.

```javascript
document.querySelector("#orders").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-cancel]");
  if (!btn) return;                       // not a cancel button: ignore
  e.preventDefault();
  cancelOrder(btn.dataset.cancel);
});

form.addEventListener("submit", (e) => {
  e.preventDefault();                    // we handle submission via fetch
  submitForm(new FormData(form));
}, { once: false });
```

## Common mistakes
- Binding a listener per row on large or dynamic lists instead of delegating once.
- Calling stopPropagation liberally and breaking unrelated features upstream.
- Leaving listeners on removed elements, leaking memory and firing ghost handlers.

## Checklist
- Are dynamic lists handled by delegation rather than per-item listeners?
- Is preventDefault/stopPropagation used only where truly needed?
- Are listeners removed or one-shot where their purpose ends?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
