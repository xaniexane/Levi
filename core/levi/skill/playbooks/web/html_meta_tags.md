---
skill_id: web_html_meta_tags
name: HTML Meta Tags
description: The meta tags that matter: charset, viewport, description, robots, and social sharing cards.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend, seo]
version: 1.0.0
---
# HTML Meta Tags
## Purpose
Control how browsers, search engines, and social platforms interpret and present your pages.
## Key ideas
- charset and viewport are functional: they affect decoding and mobile layout directly.
- The description meta often becomes the search-result snippet; write it like ad copy for the page.
- robots directives (index, noindex, follow, nofollow) guide crawlers per page.
- Open Graph and Twitter Card tags decide the title, image, and description when links are shared.
- theme-color tints browser chrome on mobile; it is small polish with real visual impact.

## In practice
Treat meta tags as the page's business card for machines: every public page gets a unique title and description, and every shareable page gets Open Graph tags with an image at the recommended dimensions. Test share cards with the platforms' debugger tools before launch; a broken image or missing title is the first impression for everyone who sees the link secondhand. Keep the head lean otherwise: each meta tag should justify its bytes, and anything page-specific beats anything copied blindly from a template. Remember crawlers read the raw HTML, so meta tags must be in the server-rendered markup, not injected late by JavaScript.

```html
<meta name="description" content="Track every order from warehouse to doorstep in real time.">
<meta name="robots" content="index, follow">
<meta property="og:title" content="Acme Order Tracking">
<meta property="og:description" content="Real-time tracking for every order.">
<meta property="og:image" content="https://acme.example/img/share.png">
<meta property="og:url" content="https://acme.example/track">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b1020">
```

## Common mistakes
- Duplicating the same title and description across every page, wasting the snippet in search results.
- Skipping share images, so links unfurl as grey boxes that nobody clicks.
- Relying on client-side JavaScript to inject meta tags that crawlers never execute.

## Checklist
- Does each public page have a unique title and description?
- Are Open Graph tags with a proper share image present on shareable pages?
- Are meta tags in the server-rendered HTML, not injected by JS?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
