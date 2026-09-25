---
skill_id: utility.json_pretty_print
name: JSON Pretty Print
description: Parse JSON and display it indented and readable - a strict validity check too.
risk: low
permissions: []
requires_confirmation: false
tags: [json, format, validate]
version: 1.0.0
---

# JSON Pretty Print

JSON Pretty Print parses a JSON document strictly and prints it back with 2-space indentation. If the input is malformed, it fails loudly with the exact error - which is half the point.

## When to use

- Reading minified JSON a human can actually scan.
- Verifying a JSON file is valid before using it.
- Inspecting an API response saved to disk.

## Steps

1. Load the input with json.load - strict parsing, no leniency.
2. Re-serialize with indent=2 and sort_keys only if you ask for it.
3. Display the result; for huge files, page it or print a subtree.
4. On parse failure, report the line, column, and message - then stop.

## Honest limits

- Standard library only (json).
- Strict by design: trailing commas and comments are errors, not features.
- Display only - the source file is never rewritten.

Original work authored for LEVI - utilities pack.
