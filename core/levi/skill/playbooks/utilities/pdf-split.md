---
skill_id: utility.pdf_split
name: PDF Split
description: Split one PDF into several files by page ranges you define.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, split, documents]
version: 1.0.0
---

# PDF Split

PDF Split carves a single PDF into multiple output files along page ranges you specify, like 1-3, 4-7, 8-end. The source file is left untouched.

## When to use

- Breaking a long report into per-chapter files.
- Extracting a few pages to send someone without the whole document.
- Separating a scanned batch back into individual documents.

## Steps

1. Open the source with pypdf's PdfReader and note the total page count.
2. Define your ranges using 1-based page numbers (humans count from 1; code counts from 0 - convert carefully).
3. For each range, create a fresh PdfWriter, add exactly those pages, and write a new file.
4. Verify each output opens and holds the expected page count.
5. Name outputs so the range is visible, e.g. report-p01-03.pdf.

## Honest limits

- Requires the third-party package pypdf (pip install pypdf).
- Scanned pages split fine but remain images - splitting does not add text.
- Double-check range boundaries; an off-by-one drops or duplicates a page.

Original work authored for LEVI - utilities pack.
