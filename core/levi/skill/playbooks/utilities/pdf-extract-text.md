---
skill_id: utility.pdf_extract_text
name: PDF Extract Text
description: Pull the text layer out of a PDF into a plain .txt file, page by page.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, extract, text]
version: 1.0.0
---

# PDF Extract Text

PDF Extract Text reads each page's embedded text and writes it to a UTF-8 .txt file, one page after another. It never alters the PDF.

## When to use

- Getting quotable text out of a report.
- Feeding a document's words into search, notes, or analysis.
- Checking what text a PDF actually contains before deciding on OCR.

## Steps

1. Open the PDF with pypdf's PdfReader.
2. For each page, call extract_text() and collect the result; note pages that come back empty.
3. Write the collected text to a .txt file, with a page-break marker between pages.
4. If most pages are empty, the PDF is scanned images - stop here and use PDF OCR instead.

## Honest limits

- Requires the third-party package pypdf (pip install pypdf).
- Multi-column layouts and tables often extract in jumbled reading order - proofread before quoting.
- Image-only pages yield nothing; that is a signal, not a failure.

Original work authored for LEVI - utilities pack.
