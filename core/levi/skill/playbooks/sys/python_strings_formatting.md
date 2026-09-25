---
skill_id: sys_python_strings_formatting
name: Python Strings and Formatting
description: Text handling: immutability, methods, f-strings, and the encode/decode boundary.
risk: info
permissions: []
requires_confirmation: false
tags: [python, language]
version: 1.0.0
---
# Python Strings and Formatting

## Purpose

Text handling: immutability, methods, f-strings, and the encode/decode boundary.

## Overview

Python strings are immutable sequences of Unicode code points. Every 'modification' - upper(), replace(), strip() - returns a new string, so chained calls are the norm and in-place edits are impossible. The str type is for text; bytes is for raw data, and the boundary between them is explicit: text.encode() produces bytes, bytes.decode() produces text, and mixing them raises TypeError. Always know your encoding - UTF-8 is the sane default - because decode errors at system boundaries are a top source of crashes in networking and file code. For building strings, f-strings are the modern choice: f"{value:.2f}" interpolates and formats in one readable pass, with format specs for width, precision, alignment, and thousands separators. str.join() is the efficient way to concatenate many pieces (repeated + in a loop is quadratic), and str.split()/rsplit()/partition() carve text apart. Useful predicates - startswith, endswith, isdigit - plus find/index round out everyday parsing; reach for the re module only when the pattern truly needs regular expressions. Triple-quoted strings hold multiline text, and raw strings (r"...") keep backslashes literal for regexes and Windows paths. Remember: methods do not mutate, so s.strip() alone does nothing - assign or use the result.

## Quick reference

- str is immutable Unicode text; bytes is immutable raw data.

- Encode text->bytes with .encode('utf-8'); decode bytes->text with .decode('utf-8').

- f-strings: f"{x:.2f}", f"{x:>10}", f"{x:,}" for precision/align/separators.

- Efficient concat: ''.join(pieces). Splitting: .split(), .rsplit(), .partition().

- String methods return new strings; they never modify in place.

- Raw strings r'...' keep backslashes literal - use for regex patterns.

- strip()/lstrip()/rstrip() trim whitespace or a char set from the ends.


## Worked example

f-strings, join, and the text/bytes boundary:

```
name, score = 'Ada', 93.456
print(f'{name:<8} scored {score:.1f}')
print(f'{"total":>10}: {1234567:,}')

parts = ['alpha', 'beta', 'gamma']
print(' | '.join(parts))

text = 'caf\u00e9'
raw = text.encode('utf-8')
print(raw, raw.decode('utf-8'))
```

- {name:<8} left-aligns in width 8; {1234567:,} adds thousands separators.

- join on the separator is linear; += in a loop is quadratic.

- encode/decode with explicit 'utf-8' avoids platform-default surprises.


## Common mistakes

- Decoding network bytes with the wrong encoding, producing mojibake.
  Fix: Agree on UTF-8 end to end; decode once at the boundary, encode once on send.

- Comparing str to bytes, or concatenating them: TypeError.
  Fix: Convert at the boundary so the program core handles one type.


## Quick checks

Q: Why does s.strip() seem to do nothing?
A: Strings are immutable: strip() returns the trimmed copy and leaves s unchanged. You must use the result - s = s.strip() - or pass it along. This applies to every str method: upper, replace, split results, all of them.


Q: When is + okay for building strings?
A: For a few known pieces it is fine and readable. In a loop over many pieces, each + copies the growing string, giving O(n^2) behavior - collect pieces in a list and join once instead.


## Mental model

A string is a printed sentence on paper: you cannot push the letters around, you can only photocopy it with changes (upper, replace) and keep the copy you like. Bytes are the same sentence as a fax signal - to read it you must decode it back into letters first.
