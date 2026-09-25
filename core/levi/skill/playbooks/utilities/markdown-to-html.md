---
skill_id: utility.markdown_to_html
name: Markdown to HTML
description: Convert a Markdown file into a standalone HTML file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [markdown, html, convert]
version: 1.0.0
---

# Markdown to HTML

Markdown to HTML renders your .md into a complete HTML document with the usual extensions (tables, fenced code blocks), written to a new .html file.

## When to use

- Publishing notes as a web page.
- Previewing Markdown with real styling.
- Feeding rendered HTML into another tool.

## Steps

1. Read the Markdown source.
2. Convert with the markdown package, enabling the tables and fenced_code extensions.
3. Wrap the fragment in a minimal HTML shell with a readable stylesheet.
4. Write the .html file and open it in a browser to confirm rendering.

## Honest limits

- Requires the third-party markdown package (pip install markdown).
- Raw HTML inside the source passes through untouched - do not run this on untrusted Markdown you plan to serve.
- Relative image paths stay relative; move images alongside the HTML.

Original work authored for LEVI - utilities pack.
