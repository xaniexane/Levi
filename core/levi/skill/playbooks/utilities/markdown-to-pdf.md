---
skill_id: utility.markdown_to_pdf
name: Markdown to PDF
description: Render a Markdown document to a styled PDF file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [markdown, pdf, convert]
version: 1.0.0
---

# Markdown to PDF

Markdown to PDF converts your .md file through HTML into a paginated PDF, with headings, code blocks, and tables intact. The Markdown source is untouched.

## When to use

- Turning documentation into a shareable PDF.
- Producing a printable version of notes or a spec.
- Handing Markdown content to someone who only opens PDFs.

## Steps

1. Install a Markdown parser (markdown) and an HTML-to-PDF renderer (weasyprint), or pandoc as an all-in-one.
2. Convert the Markdown to HTML with fenced-code and tables extensions enabled.
3. Apply basic print CSS (margins, heading sizes, code font) so the PDF looks deliberate.
4. Render to a new .pdf file and open it: check page breaks, code wrapping, and table widths.

## Honest limits

- No standard-library path exists - a third-party renderer is genuinely required.
- Complex layouts (multi-column, floats) are out of scope; this is documents, not desktop publishing.
- Always proof the PDF; Markdown edge cases render differently across engines.

Original work authored for LEVI - utilities pack.
