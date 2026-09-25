---
skill_id: utility.pdf_watermark
name: PDF Watermark
description: Stamp every page of a PDF with a text watermark such as DRAFT or CONFIDENTIAL.
risk: moderate
permissions: []
requires_confirmation: true
tags: [pdf, watermark, documents]
version: 1.0.0
---

# PDF Watermark

PDF Watermark overlays a repeated text stamp - DRAFT, CONFIDENTIAL, a date - onto each page of a PDF and writes a new file. The original stays clean.

## When to use

- Marking pre-release documents as DRAFT.
- Stamping CONFIDENTIAL on files leaving your machine.
- Adding a review date across every page of a report.

## Steps

1. Create a one-page watermark PDF holding your stamp text (reportlab works, or any tool that makes a PDF).
2. Open the target with pypdf and merge the watermark page onto every content page.
3. Write the stamped result to a new file; keep the unstamped original.
4. Open the output and check the stamp is legible but does not hide body text.

## Honest limits

- Requires pypdf plus something that can author the watermark page (e.g. reportlab).
- The stamp is baked into the pages - it is not removable metadata.
- Light gray, diagonal, modest size: a watermark should warn, not blind.

Original work authored for LEVI - utilities pack.
