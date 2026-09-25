---
skill_id: sys_linux_grep_sed_awk
name: Linux grep, sed, and awk
description: The text-processing trio: searching, stream editing, and field processing.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, shell]
version: 1.0.0
---
# Linux grep, sed, and awk

## Purpose

The text-processing trio: searching, stream editing, and field processing.

## Overview

grep searches: grep pattern file prints matching lines; -i ignores case, -v inverts, -n shows line numbers, -r recurses directories, -E enables extended regex, -F treats the pattern as a fixed string (faster, no escaping surprises), -o prints only the match, -c counts. Prefer -F for literal strings - most 'grep is slow/confusing' stories are regex metacharacters in fixed text. sed edits streams: s/old/new/ substitutes (add g for all occurrences, -i for in-place file editing - with a backup suffix on anything important), d deletes lines, p prints. sed -n with p gives fine-grained extraction. awk is a field processor: awk '{print $1}' prints the first whitespace-separated field; -F: sets the delimiter; NR is the line number, NF the field count; patterns like $3 > 100 filter rows; BEGIN/END blocks run before/after input for headers and totals. The progression: grep to find, sed to transform lines, awk when columns and arithmetic enter. For structured data (JSON/CSV) these are the wrong tools - jq and csv-aware tools beat regex on structure every time. Quote your patterns (single quotes) so the shell does not eat them.

## Quick reference

- grep -i/-v/-n/-r/-E/-F/-o/-c: the essential flags. -F for literal strings.

- sed 's/old/new/g': substitute. -i: in-place (backup first). d: delete lines.

- awk '{print $1}': fields. -F: delimiter. NR/NF: line/field counts.

- awk '$3 > 100': row filtering. BEGIN/END: setup and summary.

- grep finds, sed transforms lines, awk handles columns and math.

- Structured data (JSON/CSV) needs jq/csv tools, not regex.


## Worked example

Finding, transforming, and summarizing logs:

```
# Errors, case-insensitive, with line numbers:
grep -in 'error' app.log | head

# Mask emails in place (keep a backup):
sed -i.bak -E 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+/[redacted]/g' users.txt

# Total of the 3rd column for lines where the 2nd field is OK:
awk -F, '$2 == "OK" {sum += $3} END {print sum}' data.csv
```

- -i ignores case; -n prefixes matches with line numbers.

- -i.bak edits in place but keeps users.txt.bak as a safety copy.

- awk -F, splits on commas; END prints the accumulated total once.


## Common mistakes

- Unquoted patterns: the shell expands * before grep sees it.
  Fix: Single-quote every pattern: grep 'a*b' file.

- sed -i without backup on a one-shot transform of precious data.
  Fix: Use -i.bak, or redirect to a new file and diff before replacing.


## Quick checks

Q: grep is matching too much - what is happening?
A: Regex metacharacters in your pattern (. * [ ] etc.). If the pattern is literal text, grep -F disables regex entirely - faster and predictable.


Q: sed vs awk - how do I choose?
A: sed for line-oriented substitution/deletion. awk when you need fields, conditions on columns, or arithmetic. If you are fighting either, the task may want a real scripting language.


## Mental model

grep is a highlighter pen, sed is find-and-replace in a word processor, awk is a spreadsheet that reads text columns. You highlight first to see what you have, replace to fix it, and reach for the spreadsheet when you need to add up column C where column B says OK.
