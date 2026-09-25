---
skill_id: utility.csv_clean_headers
name: CSV Clean Headers
description: Normalize a CSV's header row to clean snake_case names and write a cleaned copy.
risk: moderate
permissions: []
requires_confirmation: true
tags: [csv, headers, cleaning]
version: 1.0.0
---

# CSV Clean Headers

CSV Clean Headers rewrites just the header row - lowercased, spaces to underscores, stray characters stripped - and writes a cleaned CSV. Data rows are copied byte-for-byte.

## When to use

- Preparing a CSV for import into a database or script.
- Fixing headers like 'First Name (required)' into first_name.
- Standardizing column names across several files.

## Steps

1. Read the header row and show the proposed renames for approval.
2. Normalize: strip, lowercase, replace spaces and dashes with underscores, drop other punctuation.
3. If two headers normalize to the same name, suffix the later ones (_2, _3) and report it.
4. Write the cleaned header plus untouched data rows to a new file.
5. Diff the headers old-vs-new to confirm nothing unexpected changed.

## Honest limits

- Only the header row is modified; every data row passes through unchanged.
- Downstream consumers using the old names must be updated - renaming is a contract change.
- Keep the original file until the cleaned one is proven good.

Original work authored for LEVI - utilities pack.
