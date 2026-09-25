---
skill_id: utility.pdf_merge
name: PDF Merge
description: Combine several PDF files into one document, in the order you name them.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, merge, documents]
version: 1.0.0
---

# PDF Merge

PDF Merge takes a list of PDF files and stitches them into a single PDF, page order following the order you give. The inputs are never touched; the result is a new file.

## When to use

- Bundling chapters, reports, or scans into one hand-off document.
- Joining a cover page to an existing PDF.
- Assembling per-section exports into a final deliverable.

## Steps

1. List the input files in final order and confirm every one opens cleanly.
2. Create a PdfWriter (pypdf) and append each input's pages in order.
3. Write the result to a NEW path - never overwrite one of the inputs.
4. Re-open the output and verify the page count equals the sum of the inputs.
5. Spot-check the first and last page of each joined section.

## Honest limits

- Requires the third-party package pypdf (pip install pypdf); the standard library cannot do this.
- Password-protected inputs must be unlocked first - have the passwords ready.
- Interactive form fields and some bookmarks may not survive the merge; verify the output.

Original work authored for LEVI - utilities pack.
