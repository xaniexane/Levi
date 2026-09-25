---
skill_id: web_css_responsive_design
name: CSS Responsive Design
description: Fluid layouts, flexible media, and media queries: designing pages that work from phones to desktops.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend, layout]
version: 1.0.0
---
# CSS Responsive Design
## Purpose
Make one codebase serve every screen by designing fluid first and adding breakpoints only where the design breaks.
## Key ideas
- Fluid layouts use relative units (%, fr, vw) so content stretches instead of snapping at fixed widths.
- Media queries apply styles conditionally: @media (min-width: 768px) targets viewports at least that wide.
- Mobile-first means base styles serve small screens and queries add complexity upward; it keeps the common path lean.
- Flexible media (max-width: 100% on images) prevents overflow; aspect-ratio preserves shape while scaling.
- Breakpoints should follow the content: add one where the layout actually breaks, not at device-specific pixels.

## In practice
Design the narrow layout first, because it forces you to decide what matters; then widen the viewport until something looks wrong and place a breakpoint there. Prefer fluid techniques (flex-wrap, grid auto-fit, clamp() for type) so many sizes need no breakpoint at all. Test at real device widths with devtools device mode, but also drag the viewport continuously; the in-between sizes are where fixed designs crack. Keep touch targets at least 44px and font sizes readable without zoom on the smallest screen you support; a responsive layout that requires pinching has failed.

```css
img, video { max-width: 100%; height: auto; }

h1 { font-size: clamp(1.5rem, 4vw, 2.5rem); }

.cards { display: grid; gap: 16px; }
@media (min-width: 640px) {
  .cards { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1024px) {
  .cards { grid-template-columns: repeat(4, 1fr); }
}
```

## Common mistakes
- Designing desktop-first and bolting on a cramped mobile view as an afterthought.
- Fixing breakpoints to specific phone models instead of where the content breaks.
- Forgetting max-width: 100% on media and shipping horizontal scrollbars on phones.

## Checklist
- Does the layout work at 360px wide without horizontal scrolling?
- Were breakpoints placed where content breaks, not at device pixels?
- Are touch targets and type sizes usable on the smallest screen?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
