---
skill_id: utility.xlsx_csv_import
name: XLSX CSV Import
description: Convert a CSV file into a proper .xlsx workbook with light type detection.
risk: moderate
permissions: []
requires_confirmation: true
tags: [excel, xlsx, csv, import]
version: 1.0.0
---

# XLSX CSV Import

XLSX CSV Import reads a CSV file and writes it as a real .xlsx workbook, converting obvious numbers to numeric cells so formulas and sorting work.

## When to use

- Upgrading a CSV export into a formatted workbook.
- Preparing CSV data for charts and pivot summaries.
- Handing tabular data to someone who works in Excel.

## Steps

1. Sniff the CSV dialect (delimiter, quoting) with csv.Sniffer on a sample.
2. Read all rows with the csv module.
3. Create a workbook with openpyxl and write rows, coercing plain integers and floats to numbers.
4. Freeze the header row and set a reasonable column width pass.
5. Save as .xlsx and open to confirm numbers sort numerically, not alphabetically.

## Honest limits

- Requires the third-party package openpyxl (pip install openpyxl).
- Dates stay text unless you parse them explicitly - decide the date format up front.
- Very large CSVs convert row by row and take a while; this is normal.

Original work authored for LEVI - utilities pack.
