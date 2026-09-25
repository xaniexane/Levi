---
skill_id: sys_python_json_csv
name: Python JSON and CSV
description: Structured text interchange: json for nested data, csv for tables.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python JSON and CSV

## Purpose

Structured text interchange: json for nested data, csv for tables.

## Overview

JSON is the lingua franca of nested data: json.dumps(obj) serializes dicts/lists/str/numbers to a string, json.loads(s) parses back. Only those basic types round-trip natively - datetimes, sets, and custom objects need a default= hook or manual conversion to strings/lists first. indent=2 makes human-readable output for configs and debugging; sort_keys=True stabilizes diffs. json.load/json.dump work directly on file objects. CSV is for flat tables: csv.reader yields rows as lists, csv.DictReader maps them through the header row into dicts - prefer DictReader, since positional columns rot when files gain a column. Always open CSV files with newline='' (the csv module handles line endings itself) and an explicit encoding. Writing: csv.writer/csv.DictWriter with writerow(s). Defensive parsing: wrap loads in try/except json.JSONDecodeError, validate the shape (is it a dict? are the keys present?) before use, and never trust numeric precision past what floats hold - money belongs in strings or integer cents. For untrusted JSON at scale, consider size limits before parsing; deeply nested payloads can exhaust the parser's recursion.

## Quick reference

- json.dumps/loads: str round-trip. json.dump/load: file objects.

- Only dict/list/str/num/bool/None round-trip natively; convert the rest.

- indent=2 for readable output; sort_keys=True for stable diffs.

- csv.DictReader: rows as dicts via header - immune to column reordering.

- Open CSV files with newline='' and an explicit encoding.

- Validate parsed shape before use; catch json.JSONDecodeError.


## Worked example

JSON round-trip and DictReader parsing:

```
import json, csv, io

payload = {'name': 'ada', 'scores': [88, 95]}
text = json.dumps(payload, indent=2, sort_keys=True)
back = json.loads(text)
assert back == payload

csv_text = 'name,score\nada,88\nbo,95\n'
rows = list(csv.DictReader(io.StringIO(csv_text)))
print(rows[0]['name'], rows[0]['score'])
```

- sort_keys=True keeps output diff-stable across runs.

- DictReader uses the header row: rows are dicts, not position lists.

- io.StringIO stands in for a file object in the example.


## Common mistakes

- json.loads on untrusted input without size/shape validation.
  Fix: Bound the input size and validate the resulting structure before use.

- Positional csv.reader indexing that breaks when columns reorder.
  Fix: Use DictReader keyed by header names.


## Quick checks

Q: How do I serialize a datetime to JSON?
A: Convert explicitly: obj.isoformat() on the way out, datetime.fromisoformat on the way in - or pass default=str to dumps for quick debugging output. Keep the conversion at the boundary so the core works with real datetimes.


Q: Why does my CSV parse break on some machines?
A: Usually line endings or encoding. Open with newline='' and encoding='utf-8-sig' (handles BOMs), and let the csv module own newline handling instead of fighting it.


## Mental model

JSON is a set of labeled moving boxes that nest inside each other; CSV is a spreadsheet with one header row. json.loads unpacks the boxes, DictReader reads the spreadsheet by column name instead of counting columns with your finger.
