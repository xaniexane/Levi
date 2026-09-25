---
skill_id: utility.xlsx_pivot_table
name: XLSX Pivot Table
description: Summarize spreadsheet data into a pivot-style summary sheet grouped by your chosen fields.
risk: moderate
permissions: []
requires_confirmation: true
tags: [excel, xlsx, pivot, analysis]
version: 1.0.0
---

# XLSX Pivot Table

XLSX Pivot Table reads a data sheet, groups rows by the fields you pick, aggregates a value column (sum, count, average), and writes the summary as a new sheet - plus an optional native Excel pivot table.

## When to use

- Summarizing sales by region and month.
- Counting tickets by status and owner.
- Averaging scores grouped by any category column.

## Steps

1. Open the workbook with openpyxl and confirm which sheet and columns hold the data.
2. Choose the row field (group by), an optional column field, and the value field with its aggregation.
3. Aggregate in Python over the rows - this summary-sheet route is the reliable one.
4. Write the summary to a new sheet with clear headers.
5. Optionally build a native pivot table via openpyxl's pivot support for interactive use in Excel.
6. Save to a new file and sanity-check a few totals by hand.

## Honest limits

- Requires the third-party package openpyxl (pip install openpyxl).
- Native pivot tables via openpyxl need a defined Table and pivot cache - fiddly; the summary sheet is the dependable deliverable.
- Dirty data (mixed types in one column, blank group cells) skews aggregates - clean first.

Original work authored for LEVI - utilities pack.
