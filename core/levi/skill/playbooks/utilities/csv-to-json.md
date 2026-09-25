---
skill_id: utility.csv_to_json
name: CSV to JSON
description: Convert a CSV file into a JSON array of objects keyed by the header row.
risk: moderate
permissions: []
requires_confirmation: true
tags: [csv, json, convert]
version: 1.0.0
---

# CSV to JSON

CSV to JSON reads a CSV with the standard csv module and writes a UTF-8 JSON array where each row becomes an object keyed by the cleaned header names.

## When to use

- Feeding CSV data to an API or tool that speaks JSON.
- Converting tabular exports for a JavaScript workflow.
- Archiving table data in a self-describing format.

## Steps

1. Read the CSV with csv.DictReader using the header row as keys.
2. Coerce obvious integers and floats; leave everything else as strings.
3. Write the list of objects with json.dump (indent=2, ensure_ascii=False) to a new .json file.
4. Validate the output by loading it back and comparing row counts.

## Honest limits

- Standard library only (csv + json) - no third-party packages needed.
- Type coercion is light on purpose; ambiguous values stay strings rather than guessing wrong.
- Duplicate header names collapse in DictReader - clean headers first if needed.

Original work authored for LEVI - utilities pack.
