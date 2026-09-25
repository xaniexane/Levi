---
skill_id: web_html_tables
name: HTML Tables
description: Mark up tabular data correctly with thead, tbody, th, scope, and caption for humans and assistive tech.
risk: info
permissions: []
requires_confirmation: false
tags: [html, frontend, accessibility]
version: 1.0.0
---
# HTML Tables
## Purpose
Present genuine tabular data so both sighted users and screen readers can follow rows, columns, and headers.
## Key ideas
- Tables are for tabular data, not layout; CSS handles layout now.
- <thead>, <tbody>, and <tfoot> group rows so headers repeat and styling targets structure.
- <th> with scope=col or scope=row tells assistive tech which cells are headers for which data.
- <caption> names the table's purpose; it is the table's heading for screen readers.
- Complex tables with merged cells need headers and id associations, but simpler tables are almost always better.

## In practice
Before reaching for a table, confirm the data is genuinely two-dimensional: if each row is an independent card, use a list instead. Write the header row with th and scope, add a caption that says what the table shows, and keep the column count modest; wide tables break mobile layouts and force horizontal scrolling. For sortable tables, make the th a button that announces its sort state. Test with a screen reader once: hearing 'row 3, column Total, $42.00' confirms your headers are wired correctly in a way sighted testing never can.

```html
<table>
  <caption>Order totals by month</caption>
  <thead>
    <tr><th scope="col">Month</th><th scope="col">Orders</th><th scope="col">Total</th></tr>
  </thead>
  <tbody>
    <tr><th scope="row">January</th><td>120</td><td>$4,310</td></tr>
    <tr><th scope="row">February</th><td>98</td><td>$3,870</td></tr>
  </tbody>
</table>
```

## Common mistakes
- Using tables for page layout, creating markup that linearizes into nonsense for screen readers.
- Marking header cells as td, so assistive tech cannot associate data with its headers.
- Omitting caption and scope, leaving the table's purpose and structure unannounced.

## Checklist
- Is the content truly tabular, not a list of cards forced into a grid?
- Do header cells use th with correct scope?
- Does a caption describe what the table contains?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
