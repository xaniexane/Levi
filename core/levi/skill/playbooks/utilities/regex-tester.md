---
skill_id: utility.regex_tester
name: Regex Tester
description: Test a regular expression against sample text and show every match and group.
risk: info
permissions: []
requires_confirmation: false
tags: [regex, testing, text]
version: 1.0.0
---

# Regex Tester

Regex Tester compiles your pattern, runs it over sample text you provide, and shows each match with its captured groups - plus a clear error if the pattern does not compile.

## When to use

- Debugging a pattern before putting it in code.
- Checking a validation regex against good and bad samples.
- Learning what a tricky pattern actually matches.

## Steps

1. Take the pattern and one or more sample strings, including samples that should NOT match.
2. Compile with re; on re.error, report the exact error and stop.
3. Show every match with its span and captured groups.
4. Test edge cases: empty string, minimal match, and adversarial input.

## Honest limits

- Standard library only (re).
- A test harness, not a proof - passing samples do not guarantee the pattern is correct in production.
- Nested quantifiers can hang on long input (catastrophic backtracking); the skill warns when it sees the shape.

Original work authored for LEVI - utilities pack.
