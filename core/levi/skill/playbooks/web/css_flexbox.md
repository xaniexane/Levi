---
skill_id: web_css_flexbox
name: CSS Flexbox
description: One-dimensional layout with flex: axes, alignment, growing, shrinking, and wrapping.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend, layout]
version: 1.0.0
---
# CSS Flexbox
## Purpose
Lay out rows and columns that adapt: navbars, card rows, and centered content without fragile hacks.
## Key ideas
- Flexbox lays out along one axis: the main axis (row or column) and the perpendicular cross axis.
- justify-content aligns along the main axis; align-items aligns along the cross axis.
- flex-grow distributes free space, flex-shrink absorbs overflow, flex-basis sets the starting size.
- flex-wrap lets items flow onto multiple lines instead of squeezing or overflowing.
- The shorthand flex: 1 means grow, shrink, and start from zero basis: the classic equal-columns recipe.

## In practice
Reach for flexbox when items flow in a single direction: a navbar, a row of buttons, a media object with text beside an image. Set display: flex on the container, then think in axes: justify-content pushes items along the row, align-items lines them up across it. For equal-width columns use flex: 1 on each child; for a fixed sidebar plus fluid content, fix the sidebar's basis and let the content grow. Centering both ways is two declarations (justify-content: center; align-items: center) on a full-size container; learn it once and retire a dozen old hacks.

```css
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.row { display: flex; gap: 12px; flex-wrap: wrap; }
.row > .card { flex: 1 1 200px; } /* grow, shrink, 200px basis */

.center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}
```

## Common mistakes
- Using flexbox for full page grids with rows and columns; that is grid's job.
- Forgetting flex-wrap and watching items squeeze into unreadable slivers on narrow screens.
- Setting fixed widths on flex children and defeating the flexibility the layout was chosen for.

## Checklist
- Is the layout truly one-dimensional (flex) or two-dimensional (grid)?
- Does the container wrap or scroll gracefully at narrow widths?
- Are alignment properties on the right axis (justify = main, align = cross)?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
