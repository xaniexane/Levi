---
skill_id: sys_python_regex
name: Python Regular Expressions
description: Pattern matching with re: when regex is right, and how to keep it readable.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python Regular Expressions

## Purpose

Pattern matching with re: when regex is right, and how to keep it readable.

## Overview

Regular expressions match text by pattern. re.search finds the first match anywhere; re.match anchors at the start; re.fullmatch requires the whole string; re.findall returns all matches; re.sub replaces them. Always write patterns as raw strings (r'\d+') so backslashes survive. Core syntax: . any char, \d \w \s classes, * + ? quantifiers, {m,n} ranges, ^ $ anchors, [...] sets, (...) groups, | alternation. Groups capture: m.group(1) or named (?P<name>...) with m.group('name'). Compile once with re.compile when a pattern runs in a loop - it caches, but explicit compilation documents intent. re.VERBOSE lets you write multi-line patterns with comments, the antidote to unreadable regex. Know the limits: regex cannot parse nested structures (HTML, JSON, code) - use a real parser. Catastrophic backtracking (nested quantifiers like (a+)+) can hang on hostile input; prefer possessive-like restraint, atomic grouping via the regex module, or simple string methods. For validation, fullmatch plus a length cap beats a clever monster pattern. And for fixed strings, in or str.startswith beats regex on both clarity and speed.

## Quick reference

- re.search: anywhere. re.match: start. re.fullmatch: whole string.

- Raw strings r'...' for patterns; re.compile for hot loops.

- Groups: (...) numbered, (?P<name>...) named. m.group('name') retrieves.

- re.VERBOSE: multi-line commented patterns for readability.

- Never parse nested formats (HTML/JSON) with regex; use a real parser.

- Beware nested quantifiers: catastrophic backtracking on hostile input.

- Fixed string? Use in / startswith - clearer and faster than regex.


## Worked example

Validation with fullmatch and named groups:

```
import re

DATE = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})')

def parse_date(text):
    m = DATE.fullmatch(text.strip())
    if not m:
        raise ValueError(f'not a date: {text!r}')
    return {k: int(v) for k, v in m.groupdict().items()}

print(parse_date('2026-09-22'))
```

- fullmatch rejects partial matches like 'xx2026-09-22yy'.

- Named groups make the extraction self-documenting.

- Validation still needs range checks (month 13 passes the pattern).


## Common mistakes

- Forgetting the raw string: '\d' becomes an escape mess.
  Fix: Always write patterns as r'...' raw strings.

- Using re.match when fullmatch semantics were intended.
  Fix: match anchors only the start; trailing garbage still passes.


## Quick checks

Q: Why do people say not to parse HTML with regex?
A: HTML nests arbitrarily and regex cannot count nesting depth - any pattern breaks on some valid document. Parsers (html.parser, BeautifulSoup, lxml) build the actual tree and handle the edge cases.


Q: What causes catastrophic backtracking?
A: Nested quantifiers like (a+)+$ on input that almost matches: the engine tries exponentially many ways to partition the string. Fix by simplifying the pattern, anchoring tightly, or avoiding regex for the task.


## Mental model

A regex is a stencil: it describes the shape of the text you want, and the engine slides it along the string looking for a fit. Groups are labeled cutouts that keep what fell through. A bad stencil (nested quantifiers) is one with a thousand overlapping cutouts - sliding it takes forever.
