---
skill_id: web_html_accessibility_basics
name: HTML Accessibility Basics
description: The highest-impact accessibility habits: alt text, focus, contrast, labels, and keyboard operability.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend, accessibility]
version: 1.0.0
---
# HTML Accessibility Basics
## Purpose
Cover the small set of practices that fix the majority of accessibility barriers on typical pages.
## Key ideas
- Images need alt text describing their purpose; decorative images get empty alt so they are skipped.
- All interactive elements must be reachable and operable by keyboard, with a visible focus indicator.
- Color contrast must meet minimum ratios; never convey information by color alone.
- Form controls need labels, error messages need association with their fields, and status updates need live regions.
- ARIA fills gaps in native semantics but never replaces them; a real button beats a div with a role.

## In practice
Build accessibility in from the first markup, because retrofitting is where it gets expensive. Tab through every new page with the keyboard: if you cannot reach it, see where you are, or operate it, neither can a keyboard user. Write alt text that answers 'what would I miss if this image vanished' rather than describing pixels. Pair every color-coded signal with text or an icon so color-blind users get the same information. Add one automated check to CI and one manual keyboard pass per feature; together they catch the vast majority of issues before users do.

```html
<img src="chart.png" alt="Bar chart: orders doubled from January to June">

<button type="button" aria-expanded="false" aria-controls="menu">Menu</button>

<div role="status" aria-live="polite" id="toast"></div>

<label for="qty">Quantity</label>
<input type="number" id="qty" aria-describedby="qty-help">
<p id="qty-help">Maximum 99 per order.</p>
```

## Common mistakes
- Removing focus outlines for aesthetics, making keyboard navigation invisible.
- Writing alt text like 'image123.png' or stuffing keywords instead of describing purpose.
- Using ARIA roles on elements that already have the semantics natively, adding complexity without benefit.

## Checklist
- Can the whole page be used with keyboard alone, with visible focus?
- Does every meaningful image have purposeful alt text?
- Is information ever carried by color alone?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
