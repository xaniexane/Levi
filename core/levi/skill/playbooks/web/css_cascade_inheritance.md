---
skill_id: web_css_cascade_inheritance
name: CSS Cascade and Inheritance
description: Which properties inherit, how the cascade resolves conflicts, and the keywords that control both.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend]
version: 1.0.0
---
# CSS Cascade and Inheritance
## Purpose
Use the cascade as a tool instead of fighting it: set globals once and override narrowly.
## Key ideas
- Inheritance passes some properties (color, font, line-height) from parent to child automatically.
- Layout properties (margin, padding, border, width) do not inherit; each element starts fresh.
- The cascade resolves conflicts by origin, then importance, then specificity, then source order.
- Keywords inherit, initial, unset, and revert let you explicitly control inheritance per property.
- Custom properties (CSS variables) inherit like normal properties, which is what makes theming work.

## In practice
Set document-wide defaults on the root or body: font family, base size, line height, text color; let inheritance carry them everywhere instead of repeating declarations. Override narrowly at the component level, and reach for the explicit keywords when you need to opt out: revert is handy for undoing a library's aggressive reset on one subtree. Because custom properties inherit, define theme tokens once on :root and override them on a subtree to re-theme a whole section with a single class. Debugging 'where did this style come from' is a devtools computed-styles question; the struck-through rules tell the cascade's story.

```css
:root {
  --ink: #1a1a1a;
  --accent: #2563eb;
  font-family: system-ui, sans-serif;
  color: var(--ink);
  line-height: 1.5;
}

.dark { --ink: #f0f0f0; --accent: #7aa5ff; }

.reset-me { all: revert; } /* opt this subtree out of author styles */
```

## Common mistakes
- Repeating font and color declarations on every component instead of inheriting document defaults.
- Assuming layout properties inherit and wondering why child margins are zero.
- Fighting a library's styles with heavier selectors instead of scoping or reverting.

## Checklist
- Are document defaults set once and inherited, not repeated?
- Do you know which of your properties inherit and which do not?
- Are theme overrides done via inherited custom properties?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
