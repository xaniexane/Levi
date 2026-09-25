---
skill_id: utility.docx_create_report
name: DOCX Create Report
description: Build a formatted Word document from a title, sections, and tables.
risk: moderate
permissions: []
requires_confirmation: true
tags: [word, docx, reports]
version: 1.0.0
---

# DOCX Create Report

DOCX Create Report assembles a .docx file from your outline: a title, headed sections of prose, and data tables. It writes a new file ready to open in Word or LibreOffice.

## When to use

- Turning an outline and numbers into a presentable report.
- Generating a recurring status document from fresh data.
- Drafting a letter or memo with proper headings.

## Steps

1. Sketch the structure first: title, section headings in order, and what each table holds.
2. Create a Document (python-docx), add the title and each heading with matching heading styles.
3. Add body paragraphs under each heading, keeping one idea per paragraph.
4. Build tables with add_table(), fill cells row by row, and apply a built-in table style.
5. Save to the named path and open the result to confirm headings, tables, and page flow.

## Honest limits

- Requires the third-party package python-docx (pip install python-docx).
- python-docx authors documents; it cannot render them to PDF or show you a preview - open the file to check.
- Heavily styled templates may shift slightly; keep formatting simple for best fidelity.

Original work authored for LEVI - utilities pack.
