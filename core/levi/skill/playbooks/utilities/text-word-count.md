---
skill_id: utility.text_word_count
name: Text Word Count
description: Count words, characters, and lines in a text file and display the totals.
risk: info
permissions: []
requires_confirmation: false
tags: [text, count, statistics]
version: 1.0.0
---

# Text Word Count

Text Word Count reads a text file and reports line, word, and character counts - the honest wc-style numbers. Read-only; it changes nothing.

## When to use

- Checking a document's length against a limit.
- Getting quick stats on a log or data file.
- Verifying an export is non-empty and sane.

## Steps

1. Read the file as UTF-8 text.
2. Count lines, whitespace-split words, and characters (with and without spaces).
3. Display the totals in a small table.
4. For multiple files, show per-file counts plus a grand total.

## Honest limits

- Standard library only.
- 'Word' means whitespace-separated token - CJK text and hyphenation count differently, and that is stated, not hidden.
- Encoding errors are reported, not silently skipped.

Original work authored for LEVI - utilities pack.
