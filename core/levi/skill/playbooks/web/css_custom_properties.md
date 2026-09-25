---
skill_id: web_css_custom_properties
name: CSS Custom Properties
description: CSS variables: declaring --tokens, scoping overrides, theming, and runtime updates from JavaScript.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend]
version: 1.0.0
---
# CSS Custom Properties
## Purpose
Centralize design decisions in named tokens so a palette or spacing change is one edit, not a hundred.
## Key ideas
- Custom properties are declared with --name and read with var(--name, fallback).
- They follow normal cascade and inheritance, so a subtree can override a token for everything inside it.
- The fallback in var() keeps things working when a token is missing; use it at trust boundaries.
- JavaScript can read and write them via getComputedStyle and setProperty, enabling runtime theming.
- @property (where supported) gives them types and transition behavior for animated tokens.

## In practice
Build a token layer at :root: colors, spacing scale, radii, shadows, type scale; then write components exclusively in tokens, never raw hex codes. Theming becomes a class that redefines tokens, dark mode included, with no component changes. Keep token names semantic (--surface, --ink, --accent) rather than literal (--light-blue), because literal names lie after the next rebrand. Validate overrides by toggling the theme class in devtools and watching the whole page follow; any element that does not follow has a hard-coded value hiding somewhere.

```css
:root {
  --surface: #ffffff;
  --ink: #1a1a1a;
  --accent: #2563eb;
  --space: 16px;
  --radius: 8px;
}
.dark {
  --surface: #111318;
  --ink: #eef0f4;
  --accent: #7aa5ff;
}
.card {
  background: var(--surface);
  color: var(--ink);
  padding: var(--space);
  border-radius: var(--radius);
  border: 1px solid var(--accent, #999);
}
```

## Common mistakes
- Naming tokens after their current value (--light-blue), which rots on the first rebrand.
- Hard-coding values inside components, bypassing the token layer and breaking theming.
- Overriding tokens without fallbacks at integration points where the token may be undefined.

## Checklist
- Are all design values tokens, with components referencing tokens only?
- Do token names describe role, not current appearance?
- Does toggling a theme class re-theme the entire page?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
