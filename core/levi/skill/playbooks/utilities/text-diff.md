---
skill_id: utility.text_diff
name: Text Diff
description: Show a unified diff between two text files, read-only.
risk: info
permissions: []
requires_confirmation: false
tags: [text, diff, compare]
version: 1.0.0
---

# Text Diff

Text Diff compares two text files line by line with difflib and displays a unified diff. Nothing is written and neither file is modified.

## When to use

- Seeing exactly what changed between two versions of a file.
- Reviewing config changes before applying them.
- Comparing an expected output against an actual one.

## Steps

1. Read both files as text.
2. Produce a unified diff with difflib.unified_diff, labeled with the filenames.
3. Display the diff; keep context lines at 3 unless the files are huge.
4. For large files, summarize counts (+/- lines) before dumping the full diff.

## Honest limits

- Standard library only (difflib) - nothing to install.
- Comparison is line-based; reworded paragraphs show as full-line changes.
- Binary files are out of scope - this skill reads text.

Original work authored for LEVI - utilities pack.
