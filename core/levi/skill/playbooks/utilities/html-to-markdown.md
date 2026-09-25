---
skill_id: utility.html_to_markdown
name: HTML to Markdown
description: Convert an HTML document back into readable Markdown text.
risk: moderate
permissions: []
requires_confirmation: true
tags: [html, markdown, convert]
version: 1.0.0
---

# HTML to Markdown

HTML to Markdown parses an HTML file and rewrites it as Markdown - headings, lists, links, tables, and code preserved as far as the format allows.

## When to use

- Recovering editable text from an HTML export.
- Converting saved web pages into notes.
- Moving content from a CMS into Markdown files.

## Steps

1. Parse the HTML with a converter (html2text or markdownify).
2. Convert, keeping link targets and code fences intact.
3. Write the Markdown to a new .md file.
4. Read the result: confirm headings, lists, and links survived; fix what did not.

## Honest limits

- Requires a third-party converter (html2text or markdownify); a stdlib HTMLParser fallback loses tables and nesting - say so if you use it.
- Pixel layouts, scripts, and styles have no Markdown equivalent and are dropped by design.
- Proofread the output; conversion is lossy and proud of it.

Original work authored for LEVI - utilities pack.
