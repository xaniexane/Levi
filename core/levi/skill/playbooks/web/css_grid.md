---
skill_id: web_css_grid
name: CSS Grid
description: Two-dimensional layout with grid: tracks, areas, gaps, and responsive patterns like auto-fit.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend, layout]
version: 1.0.0
---
# CSS Grid
## Purpose
Build page-level layouts and true grids where rows and columns are designed together.
## Key ideas
- Grid lays out in two dimensions at once: define columns and rows on the container, place items into cells.
- grid-template-columns: 1fr 2fr 1fr creates three tracks with the middle twice as wide; fr is a share of free space.
- Named areas (grid-template-areas) let you draw the layout as ASCII art and assign items by name.
- repeat(auto-fit, minmax(200px, 1fr)) makes columns that wrap responsively with no media queries.
- gap sets gutters uniformly; it replaces the old margin-on-every-child dance.

## In practice
Use grid when the design has both rows and columns that relate to each other: page shells (header, sidebar, main, footer), dashboards, galleries. Sketch the layout as named areas first; the ASCII diagram doubles as documentation and makes responsive rearrangement a matter of re-drawing the diagram in a media query. For card grids, the auto-fit plus minmax pattern handles most responsive needs without breakpoints at all. Keep items' placement explicit only where it matters; auto-placement with a sensible source order covers the rest and keeps the DOM order logical for screen readers.

```css
.page {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
  gap: 16px;
}
.page > header { grid-area: header; }

.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}
```

## Common mistakes
- Reaching for grid for a simple row of items that flexbox handles with less code.
- Hard-coding many fixed breakpoints when auto-fit and minmax would adapt fluidly.
- Placing items visually out of DOM order without checking the screen-reader and tab order.

## Checklist
- Are two-dimensional relationships expressed in grid, not nested flexboxes?
- Do card grids use auto-fit/minmax before adding breakpoints?
- Does visual order still match DOM order for assistive tech?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
