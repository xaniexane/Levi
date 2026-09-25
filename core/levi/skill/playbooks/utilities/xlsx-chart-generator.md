---
skill_id: utility.xlsx_chart_generator
name: XLSX Chart Generator
description: Build a bar, line, or pie chart from a data range and embed it in the workbook.
risk: moderate
permissions: []
requires_confirmation: true
tags: [excel, xlsx, charts]
version: 1.0.0
---

# XLSX Chart Generator

XLSX Chart Generator takes a contiguous block of data in a sheet and embeds a real Excel chart object - bar, line, or pie - with titles and axis labels, saving the workbook with the chart in place.

## When to use

- Charting monthly totals from a data column.
- Adding a trend line visual to a report workbook.
- Turning a small summary table into a pie chart.

## Steps

1. Open the workbook with openpyxl and select the data range, including header row for series names.
2. Create the chart object (BarChart, LineChart, or PieChart) and attach the data range.
3. Set the chart title and axis titles so the chart explains itself.
4. Place the chart on the sheet at a chosen anchor cell, clear of the data.
5. Save and open in Excel or LibreOffice to confirm it renders.

## Honest limits

- Requires the third-party package openpyxl (pip install openpyxl).
- Charts render in Excel/LibreOffice, not in simple file previewers - open it in a real spreadsheet app to verify.
- Data must be contiguous; gaps in the range produce gaps in the chart.

Original work authored for LEVI - utilities pack.
