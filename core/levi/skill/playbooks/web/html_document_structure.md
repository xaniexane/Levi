---
skill_id: web_html_document_structure
name: HTML Document Structure
description: The anatomy of a valid HTML document: doctype, head, body, and the metadata every page should carry.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend]
version: 1.0.0
---
# HTML Document Structure
## Purpose
Start every page from a correct skeleton so browsers render in standards mode and tooling can parse your markup reliably.
## Key ideas
- The doctype <!DOCTYPE html> triggers standards mode; without it browsers fall back to quirks mode with legacy layout bugs.
- The head holds metadata invisible on the page: title, charset, viewport, stylesheets, and scripts.
- The body holds everything rendered; exactly one main landmark should describe the primary content.
- Declare charset=utf-8 first in the head so the browser decodes every later byte correctly.
- The lang attribute on <html> tells screen readers and search engines which language the page uses.

## In practice
Memorize one correct skeleton and reuse it for every page; most rendering mysteries trace back to a malformed head. Put the charset meta tag before any other content in the head, then the viewport tag for mobile, then the title. Keep render-blocking scripts out of the head or mark them defer; the page should paint before it becomes interactive, not after. Validate new templates once with a markup validator; catching a missing closing tag early beats debugging layout ghosts later.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Orders - Acme Shop</title>
  <link rel="stylesheet" href="/styles/app.css">
  <script src="/js/app.js" defer></script>
</head>
<body>
  <header>...</header>
  <main>
    <h1>Your orders</h1>
  </main>
  <footer>...</footer>
</body>
</html>
```

## Common mistakes
- Omitting the doctype and inheriting quirks-mode box model bugs that only appear in some browsers.
- Declaring the charset late or not at all, turning non-ASCII text into mojibake.
- Putting visible content in the head or metadata in the body, confusing parsers and validators.

## Checklist
- Does every page start with the HTML5 doctype and a lang attribute?
- Is charset declared first in the head, with a viewport meta for mobile?
- Are scripts deferred or at the end of body so first paint is not blocked?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
