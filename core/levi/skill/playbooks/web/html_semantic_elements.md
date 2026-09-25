---
skill_id: web_html_semantic_elements
name: HTML Semantic Elements
description: Use header, nav, main, article, section, and footer so markup describes meaning, not just appearance.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend, accessibility]
version: 1.0.0
---
# HTML Semantic Elements
## Purpose
Write markup that assistive technology, search engines, and future maintainers can understand without reading the CSS.
## Key ideas
- Semantic elements describe role: <nav> is navigation, <article> is self-contained content, <aside> is tangential.
- Screen readers offer landmark navigation built from these elements; divs give them nothing to work with.
- Exactly one <h1> per page, with headings nested in order, creates a document outline tools can follow.
- Use <button> for actions and <a> for navigation; the choice determines keyboard behavior and semantics.
- A <section> needs a heading to be meaningful; otherwise it is just a div with extra steps.

## In practice
When building a page, sketch its outline in words first: banner, navigation, main content, complementary info, footer; then pick the element that matches each region. Replace clickable divs with real buttons and links; you get keyboard support, focus styles, and correct announcements for free, while the div version needs all of it hand-built and usually gets none. Headings are not a styling tool: if it looks like a heading but is not in the outline, it is a styled paragraph. Run a screen reader or an accessibility checker over new templates; semantic gaps show up immediately.

```html
<header>
  <nav aria-label="Primary">
    <a href="/">Home</a>
    <a href="/orders">Orders</a>
  </nav>
</header>
<main>
  <article>
    <h1>Shipping update</h1>
    <p>Your order left the warehouse.</p>
    <button type="button" id="track">Track package</button>
  </article>
  <aside>
    <h2>Related</h2>
  </aside>
</main>
```

## Common mistakes
- Building the whole page from divs and spans, leaving screen readers with an undifferentiated soup.
- Using heading levels for font size, skipping from h1 to h4 and breaking the outline.
- Making divs clickable with JavaScript instead of using buttons, losing keyboard and focus behavior.

## Checklist
- Can a screen reader navigate the page by landmarks and headings?
- Are actions buttons and navigation links, not clickable divs?
- Does the heading order form a clean outline with one h1?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
