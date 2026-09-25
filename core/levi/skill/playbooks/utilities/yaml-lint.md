---
skill_id: utility.yaml_lint
name: YAML Lint
description: Scan a YAML file for structural problems like tabs and bad indentation - with honest parser limits.
risk: info
permissions: []
requires_confirmation: false
tags: [yaml, lint, validate]
version: 1.0.0
---

# YAML Lint

YAML Lint performs structural checks a real parser would also catch - tab indentation, inconsistent indent widths, duplicate keys at the same level - and reports them with line numbers. It is a linter, not a parser, and says so.

## When to use

- Catching why a YAML config refuses to load.
- Pre-checking hand-edited YAML before deployment.
- Finding tab characters that silently break YAML.

## Steps

1. Read the file line by line.
2. Flag tab indentation (YAML forbids tabs), mixed indent widths, and trailing whitespace.
3. Track mapping keys per indent level and flag duplicates.
4. Report every finding as line number plus plain-language explanation.

## Honest limits

- The standard library cannot parse YAML at all - real validation needs PyYAML installed.
- This skill finds structural smells; it cannot evaluate anchors, merges, or multi-line scalars.
- A clean lint is encouraging, not a guarantee - parse with PyYAML to be sure.

Original work authored for LEVI - utilities pack.
