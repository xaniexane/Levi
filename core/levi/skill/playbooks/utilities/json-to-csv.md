---
skill_id: utility.json_to_csv
name: JSON to CSV
description: Flatten a JSON array of objects into a CSV file with one row per object.
risk: moderate
permissions: []
requires_confirmation: true
tags: [json, csv, convert]
version: 1.0.0
---

# JSON to CSV

JSON to CSV takes a JSON array of objects and writes a CSV: the union of all keys becomes the header row, nested objects are stored as JSON strings in their cells.

## When to use

- Turning an API response into a spreadsheet-friendly file.
- Converting JSON logs into tabular form.
- Preparing JSON data for Excel import.

## Steps

1. Load the JSON and confirm it is an array of objects.
2. Collect the union of all keys across objects, in first-seen order, as the header.
3. Flatten each object: scalars as-is, nested objects/arrays serialized with json.dumps.
4. Write rows with the csv module to a new .csv file.
5. Open the result and confirm row count matches the array length.

## Honest limits

- Standard library only (json + csv).
- Deeply nested data loses structure by design - cells hold JSON strings, not sub-tables.
- Objects with wildly different keys produce sparse rows; that is honest, not broken.

Original work authored for LEVI - utilities pack.
