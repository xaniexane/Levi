---
skill_id: utility.pdf_rotate
name: PDF Rotate
description: Rotate pages of a PDF by 90, 180, or 270 degrees and save the corrected file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, rotate, documents]
version: 1.0.0
---

# PDF Rotate

PDF Rotate fixes sideways or upside-down pages - common with scans - by rotating selected pages (or all of them) and writing a corrected copy.

## When to use

- Fixing a scan batch that came out sideways.
- Straightening mixed-orientation pages before merging.
- Preparing pages for OCR, which reads best right-side up.

## Steps

1. Open the PDF and identify which pages are wrong and by how many degrees.
2. Apply rotation per page with pypdf (page.rotate(90), rotate(180), or rotate(270)).
3. Write the corrected pages to a new file; do not overwrite the source until verified.
4. Flip through the output - every page should read upright.

## Honest limits

- Requires the third-party package pypdf (pip install pypdf).
- Rotation is stored as page metadata; any standards-following viewer honors it.
- If only some pages are wrong, rotate just those - blanket rotation breaks the good ones.

Original work authored for LEVI - utilities pack.
