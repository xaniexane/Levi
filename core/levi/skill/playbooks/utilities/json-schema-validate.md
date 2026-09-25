---
skill_id: utility.json_schema_validate
name: JSON Schema Validate
description: Check a JSON document against expected structure and report every violation.
risk: info
permissions: []
requires_confirmation: false
tags: [json, schema, validate]
version: 1.0.0
---

# JSON Schema Validate

JSON Schema Validate walks a JSON document against a set of expectations - required keys, value types, allowed values - and reports each violation with its path. Read-only analysis.

## When to use

- Verifying a config file has every required field.
- Checking API payloads against a contract before trusting them.
- Catching type mistakes (a string where a number belongs).

## Steps

1. Define the expectations: required keys per object, expected types, allowed value sets.
2. Load the JSON and walk it, recording each violation as dotted.path: what was expected vs found.
3. Display all violations grouped by path; an empty report means it passed.
4. Fix the document or the expectations - this skill only reports.

## Honest limits

- Standard library only for the common checks; full JSON Schema (draft 2020-12) needs the third-party jsonschema package.
- Hand-rolled checks cover required-keys and types honestly; exotic keywords (allOf, oneOf) are out of scope without the package.
- Validation reports problems; it never mutates the document.

Original work authored for LEVI - utilities pack.
