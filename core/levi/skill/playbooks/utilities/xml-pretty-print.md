---
skill_id: utility.xml_pretty_print
name: XML Pretty Print
description: Parse XML and display it indented - a strict well-formedness check too.
risk: low
permissions: []
requires_confirmation: false
tags: [xml, format, validate]
version: 1.0.0
---

# XML Pretty Print

XML Pretty Print parses an XML document with ElementTree, indents it, and displays the result. Malformed XML fails with the parser's exact error.

## When to use

- Reading minified XML or SOAP payloads.
- Verifying an XML config is well-formed.
- Inspecting RSS/Atom feeds saved to disk.

## Steps

1. Parse with xml.etree.ElementTree - strict, no recovery mode.
2. Indent the tree and serialize with an XML declaration.
3. Display the result.
4. On failure, report the parser's line and column, then stop.

## Honest limits

- Standard library only (xml.etree.ElementTree).
- Well-formed is not the same as valid: this checks syntax, not your schema.
- Namespaces are preserved verbatim, prefixes included.

Original work authored for LEVI - utilities pack.
