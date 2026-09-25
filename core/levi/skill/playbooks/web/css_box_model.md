---
skill_id: web_css_box_model
name: CSS Box Model
description: Content, padding, border, margin: how every element's box is sized and why box-sizing changes everything.
risk: info
permissions: []
requires_confirmation: false
tags: [css, frontend]
version: 1.0.0
---
# CSS Box Model
## Purpose
End layout surprises by knowing exactly what width means and where each pixel of an element's footprint comes from.
## Key ideas
- Every element is a box: content at the center, then padding, border, and margin moving outward.
- By default, width sets only the content box; padding and border add to the total size.
- box-sizing: border-box makes width include padding and border, which matches how designers think.
- Margins collapse vertically between neighbors; padding and borders never collapse.
- Apply border-box globally with a universal selector; it is the closest thing CSS has to a consensus default.

## In practice
Start every stylesheet with the universal border-box reset and you will eliminate a whole class of 'why is this 24px wider than I said' bugs. When debugging layout, inspect the box model diagram in devtools before touching any values; most surprises are padding or margin you forgot, not broken CSS. Remember that percentage widths resolve against the containing block's content width, and that auto margins center block boxes horizontally. If an element overflows, check box-sizing first, then padding, then content; the fix is usually arithmetic, not a new technique.

```css
*, *::before, *::after { box-sizing: border-box; }

.card {
  width: 300px;        /* total width, padding and border included */
  padding: 16px;
  border: 1px solid #ccc;
  margin: 12px auto;   /* auto side margins center it */
}
```

## Common mistakes
- Mixing content-box and border-box sizing across a layout, so identical widths render differently.
- Forgetting margin collapse and adding extra spacing to compensate, which then doubles in other contexts.
- Setting widths in pixels on fluid layouts instead of letting border-box percentages do the work.

## Checklist
- Is border-box applied globally at the top of the stylesheet?
- When debugging size, do you check the devtools box diagram first?
- Are centering and spacing using margins deliberately, not accidentally?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
