---
skill_id: utility.text_remove_duplicates_lines
name: Text Remove Duplicate Lines
description: Drop repeated lines from a text file, keeping first occurrences in order.
risk: moderate
permissions: []
requires_confirmation: true
tags: [text, deduplicate, cleaning]
version: 1.0.0
---

# Text Remove Duplicate Lines

Text Remove Duplicate Lines reads a text file, keeps each distinct line the first time it appears, drops later repeats, and writes the deduplicated file with a count of removed lines.

## When to use

- Cleaning a list that accumulated repeats.
- Deduping a wordlist or blocklist.
- Tidying log excerpts down to unique lines.

## Steps

1. Read the file's lines, deciding up front whether to strip trailing whitespace before comparing.
2. Keep the first occurrence of each line; count the repeats.
3. Write the kept lines in original order to a new file.
4. Report lines in, lines out, duplicates removed.

## Honest limits

- Duplicate means exactly identical lines - 'Error' and 'Error ' differ unless you strip first.
- Order is preserved; this is not a sort.
- Confirm the counts before replacing the original.

Original work authored for LEVI - utilities pack.
