---
skill_id: utility.xlsx_formula_audit
name: XLSX Formula Audit
description: Scan a workbook's formulas and report volatile functions, external links, and errors - read-only.
risk: low
permissions: []
requires_confirmation: false
tags: [excel, xlsx, formulas, audit]
version: 1.0.0
---

# XLSX Formula Audit

XLSX Formula Audit walks every cell that holds a formula and reports what it finds: volatile functions that recalculate constantly, links to other files, and error values. It never changes the workbook.

## When to use

- Checking a inherited spreadsheet for fragile formulas before trusting it.
- Finding external links that will break when files move.
- Listing every formula in a workbook for review.

## Steps

1. Open the workbook with openpyxl in formula mode (data_only=False).
2. Walk all cells; collect each formula with its address.
3. Flag volatile functions (NOW, TODAY, RAND, OFFSET, INDIRECT) and references to other workbooks.
4. Note cells showing error values from the last calculation.
5. Display the findings grouped by sheet; write nothing.

## Honest limits

- Requires the third-party package openpyxl (pip install openpyxl).
- openpyxl does not calculate formulas - displayed values are whatever Excel saved last.
- This skill only reports; fixing the formulas is a separate, human decision.

Original work authored for LEVI - utilities pack.
