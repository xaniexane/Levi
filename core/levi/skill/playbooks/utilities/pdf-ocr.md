---
skill_id: utility.pdf_ocr
name: PDF OCR
description: Run optical character recognition on scanned PDFs so their pages gain searchable text.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, ocr, scanning]
version: 1.0.0
---

# PDF OCR

PDF OCR is for PDFs that are really just pictures of pages. It runs an OCR engine over each page and produces a searchable PDF (or plain text), so the words inside become selectable and searchable.

## When to use

- Making scanned contracts, receipts, or books searchable.
- Preparing a scan archive for text extraction.
- Fixing a PDF whose 'text' selects as nothing.

## Steps

1. First check whether the PDF already has text (try selecting a word). If it does, you do not need OCR - use PDF Extract Text.
2. Install an OCR engine: ocrmypdf (recommended) or the tesseract command-line tool.
3. Run the engine over a COPY of the scan, asking for a searchable PDF output.
4. Open the result and search for a known word to confirm the text layer exists.
5. Spot-check accuracy on one dense page before batching the rest.

## Honest limits

- Needs a real OCR engine (tesseract or ocrmypdf) - no standard-library or pure-Python substitute exists.
- Accuracy follows scan quality: clean 300 DPI scans do well, skewed phone photos do not.
- Handwriting is mostly not recognized; treat the output as a best effort.
- OCR is slow on large documents - budget time per hundred pages.

Original work authored for LEVI - utilities pack.
